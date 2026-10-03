import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from services.registry.contracts import (
    ENTITY,
    Asset,
    ConfigurationEvent,
    Device,
    Facility,
    Metric,
    Organization,
    ProductionLine,
    RegistryEntity,
    RegistryRecord,
    RegistryWrite,
    SignalMapping,
)
from simulator.factory import ASSETS, BASE_KW

if TYPE_CHECKING:
    from edge.storage.repository import Repository


class RegistryError(ValueError):
    pass


class RegistryService:
    def __init__(self, repo: "Repository") -> None:
        self.repo = repo

    def records(self) -> list[RegistryRecord]:
        with self.repo.lock:
            return [
                RegistryRecord(revision=row["revision"], entity=ENTITY.validate_json(row["body"]))
                for row in self.repo.db.execute(
                    "SELECT * FROM registry WHERE org_id=? AND facility_id=? ORDER BY kind,id",
                    (str(self.repo.org_id), str(self.repo.facility_id)),
                )
            ]

    def bootstrap(self) -> None:
        with self.repo.lock, self.repo.db:
            if self.repo.db.execute("SELECT COUNT(*) FROM registry").fetchone()[0]:
                return
            org, facility = self.repo.org_id, self.repo.facility_id
            entities: list[RegistryEntity] = [
                Organization(
                    id=str(org), org_id=org, facility_id=facility, name="Simulation organization"
                ),
                Facility(
                    id=str(facility), org_id=org, facility_id=facility, name="Synthetic factory"
                ),
                ProductionLine(
                    id="simulation-line",
                    org_id=org,
                    facility_id=facility,
                    name="Synthetic production line",
                ),
                Device(
                    id="factory-simulator-v1",
                    org_id=org,
                    facility_id=facility,
                    name="Factory simulator",
                ),
                Metric(id="active_power", org_id=org, facility_id=facility, name="Active power"),
            ]
            for i, (label, rated) in enumerate(zip(ASSETS, BASE_KW, strict=True), 1):
                entities.extend(
                    [
                        Asset(
                            id=f"SIM-{i}",
                            org_id=org,
                            facility_id=facility,
                            name=label,
                            line_id="simulation-line",
                            rated_kw=rated,
                            max_load_kw=rated * 2,
                        ),
                        SignalMapping(
                            id=f"power-{i}",
                            org_id=org,
                            facility_id=facility,
                            name=f"{label} power",
                            asset_id=f"SIM-{i}",
                            device_id="factory-simulator-v1",
                            signal_id="active-power",
                        ),
                    ]
                )
            for entity in entities:
                self._insert(entity, 1)
                self._event(
                    RegistryWrite(entity=entity, expected_revision=0, request_id=uuid4()), 1
                )

    def _insert(self, entity: RegistryEntity, revision: int) -> None:
        self.repo.db.execute(
            "INSERT INTO registry VALUES(?,?,?,?,?,?) ON CONFLICT(kind,id) DO UPDATE "
            "SET revision=excluded.revision,body=excluded.body",
            (
                entity.kind,
                entity.id,
                str(entity.org_id),
                str(entity.facility_id),
                revision,
                entity.model_dump_json(),
            ),
        )

    def _event(self, write: RegistryWrite, revision: int) -> None:
        event = ConfigurationEvent(
            sequence=self.repo.db.execute(
                "SELECT COALESCE(MAX(sequence),0)+1 FROM configuration_outbox"
            ).fetchone()[0],
            event_id=uuid4(),
            occurred_at=datetime.now(UTC),
            org_id=self.repo.org_id,
            facility_id=self.repo.facility_id,
            correlation_id=write.request_id,
            causation_id=write.request_id,
            idempotency_key=write.request_id,
            payload=RegistryRecord(entity=write.entity, revision=revision),
        )
        self.repo.db.execute(
            "INSERT INTO configuration_outbox(event_id,request_id,fingerprint,body) "
            "VALUES(?,?,?,?)",
            (
                str(event.event_id),
                str(write.request_id),
                self.fingerprint(write),
                event.model_dump_json(),
            ),
        )

    @staticmethod
    def fingerprint(write: RegistryWrite) -> str:
        return hashlib.sha256(write.model_dump_json().encode()).hexdigest()

    def save(self, write: RegistryWrite) -> RegistryRecord:
        entity = write.entity
        with self.repo.lock, self.repo.db:
            if (entity.org_id, entity.facility_id) != (self.repo.org_id, self.repo.facility_id):
                raise RegistryError("SCOPE_MISMATCH")
            replay = self.repo.db.execute(
                "SELECT fingerprint,body FROM configuration_outbox WHERE request_id=?",
                (str(write.request_id),),
            ).fetchone()
            if replay:
                if replay[0] != self.fingerprint(write):
                    raise RegistryError("IDEMPOTENCY_CONFLICT")
                return ConfigurationEvent.model_validate_json(replay[1]).payload
            records = self.records()
            prior = next(
                (r for r in records if (r.entity.kind, r.entity.id) == (entity.kind, entity.id)),
                None,
            )
            if write.expected_revision != (prior.revision if prior else 0):
                raise RegistryError("REVISION_CONFLICT")
            if (not prior and len(records) >= 100) or self.repo.db.execute(
                "SELECT COUNT(*) FROM configuration_outbox"
            ).fetchone()[0] >= 10000:
                raise RegistryError("REGISTRY_CAPACITY")
            if isinstance(entity, Organization) and (
                entity.id != str(self.repo.org_id) or not entity.enabled
            ):
                raise RegistryError("ORGANIZATION_SCOPE_FIXED")
            if isinstance(entity, Facility) and (
                entity.id != str(self.repo.facility_id) or not entity.enabled
            ):
                raise RegistryError("FACILITY_SCOPE_FIXED")
            if isinstance(entity, Metric) and (entity.id != "active_power" or not entity.enabled):
                raise RegistryError("METRIC_CATALOG_FIXED")
            combined = {(r.entity.kind, r.entity.id): r.entity for r in records}
            combined[(entity.kind, entity.id)] = entity
            if sum(len(e.model_dump_json().encode()) + 64 for e in combined.values()) > 150000:
                raise RegistryError("REGISTRY_CAPACITY")
            self.validate_relations(list(combined.values()))
            revision = write.expected_revision + 1
            self._insert(entity, revision)
            self._event(write, revision)
            return RegistryRecord(entity=entity, revision=revision)

    @staticmethod
    def validate_relations(entities: list[RegistryEntity]) -> None:
        indexed: dict[tuple[str, str], RegistryEntity] = {(e.kind, e.id): e for e in entities}
        signals: set[tuple[str, str, str]] = set()
        mapped_assets: set[str] = set()
        for entity in entities:
            refs: list[tuple[str, str]] = []
            if isinstance(entity, Asset):
                refs.append(("line", entity.line_id))
            elif isinstance(entity, SignalMapping):
                refs.extend(
                    [
                        ("asset", entity.asset_id),
                        ("device", entity.device_id),
                        ("metric", entity.metric_id),
                    ]
                )
                key = (entity.device_id, entity.asset_id, entity.signal_id)
                if entity.enabled:
                    if key in signals or entity.asset_id in mapped_assets:
                        raise RegistryError("DUPLICATE_ACTIVE_MAPPING")
                    signals.add(key)
                    mapped_assets.add(entity.asset_id)
            for ref in refs:
                parent = indexed.get(ref)
                if parent is None:
                    raise RegistryError("UNKNOWN_REFERENCE")
                if entity.enabled and not parent.enabled:
                    raise RegistryError("ENABLED_DEPENDENCY")

    def mapping(self, asset: str, device: str, signal: str) -> SignalMapping:
        for record in self.records():
            entity = record.entity
            if (
                isinstance(entity, SignalMapping)
                and entity.enabled
                and (entity.asset_id, entity.device_id, entity.signal_id) == (asset, device, signal)
            ):
                return entity
        raise RegistryError("UNMAPPED_SIGNAL")

    def events(self, after: int = 0) -> list[ConfigurationEvent]:
        with self.repo.lock:
            return [
                ConfigurationEvent.model_validate_json(row[0])
                for row in self.repo.db.execute(
                    "SELECT body FROM configuration_outbox WHERE sequence>? "
                    "ORDER BY sequence LIMIT 100",
                    (after,),
                )
            ]
