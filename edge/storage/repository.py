import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid4

from services.registry.contracts import Asset
from services.registry.service import RegistryError, RegistryService
from services.telemetry.contracts import (
    IngestResult,
    StoredPoint,
    TelemetryBatch,
    TelemetryEvent,
)


class Rejected(ValueError):
    pass


class CapacityError(ValueError):
    pass


class Repository:
    def __init__(self, path: Path | None, capacity: int = 250000) -> None:
        self.lock = RLock()
        self.capacity = capacity
        self.read_uri = (
            path.resolve().as_uri() + "?mode=ro"
            if path is not None
            else f"file:gridforge-{uuid4()}?mode=memory&cache=shared"
        )
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(
            str(path) if path else self.read_uri, uri=path is None, check_same_thread=False
        )
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=3000")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11):
            self.db.close()
            raise ValueError("Unsupported edge schema version")
        migrations = (
            "0001_telemetry.sql",
            "0002_registry.sql",
            "0003_forecasting.sql",
            "0004_optimization.sql",
            "0005_dispatch.sql",
            "0006_finance.sql",
            "0007_sync.sql",
            "0008_ai.sql",
            "0009_hardening.sql",
            "0010_reporting.sql",
            "0011_alerting.sql",
        )
        for next_version in range(version + 1, 12):
            sql = (Path(__file__).parent / "migrations" / migrations[next_version - 1]).read_text()
            self.db.executescript(
                "BEGIN IMMEDIATE;\n" + sql + f"\nPRAGMA user_version={next_version};\nCOMMIT;"
            )
        with self.db:
            for index, name in enumerate(migrations, 1):
                content = (Path(__file__).parent / "migrations" / name).read_bytes()
                checksum = hashlib.sha256(content).hexdigest()
                saved = self.db.execute(
                    "SELECT digest FROM migration_history WHERE version=?", (index,)
                ).fetchone()
                if saved and saved[0] != checksum:
                    raise ValueError("MIGRATION_CHECKSUM_MISMATCH")
                self.db.execute(
                    "INSERT OR IGNORE INTO migration_history VALUES (?,?,?)",
                    (index, checksum, datetime.now(UTC).isoformat()),
                )
            self.db.execute(
                "INSERT OR IGNORE INTO identity VALUES (1,?,?,?,0)",
                (str(uuid4()), str(uuid4()), 57),
            )
            self.db.execute(
                "INSERT OR IGNORE INTO edge_identity VALUES (1,?,?)",
                (str(uuid4()), datetime.now(UTC).isoformat()),
            )
        row = self.db.execute("SELECT * FROM identity").fetchone()
        self.org_id, self.facility_id = UUID(row["org_id"]), UUID(row["facility_id"])
        self.edge_id = UUID(self.db.execute("SELECT edge_id FROM edge_identity").fetchone()[0])
        self.seed = int(row["seed"])
        self.registry = RegistryService(self)
        self.registry.bootstrap()
        if path is not None:
            path.chmod(0o600)

    def close(self) -> None:
        self.db.close()

    def count(self, name: str, amount: int = 1) -> None:
        with self.lock, self.db:
            self.db.execute("UPDATE counters SET value=value+? WHERE name=?", (amount, name))

    def ingest(
        self, batch: TelemetryBatch, received: datetime, tick: int | None = None
    ) -> IngestResult:
        accepted = duplicates = 0
        # Scope and replay conflicts reject the entire batch, before any commit.
        with self.lock, self.db:
            size = self.db.execute("SELECT value FROM counters WHERE name='accepted'").fetchone()[0]
            for point in batch.points:
                if (point.org_id, point.facility_id) != (self.org_id, self.facility_id):
                    raise Rejected("SCOPE_MISMATCH")
                fingerprint = hashlib.sha256(point.model_dump_json().encode()).hexdigest()
                existing = self.db.execute(
                    "SELECT fingerprint FROM telemetry WHERE idempotency_key=?",
                    (str(point.idempotency_key),),
                ).fetchone()
                if existing:
                    if existing[0] != fingerprint:
                        raise Rejected("IDEMPOTENCY_CONFLICT")
                    duplicates += 1
                    continue
                if size + accepted >= self.capacity:
                    raise CapacityError("STORAGE_FULL")
                try:
                    mapping = self.registry.mapping(
                        point.asset_id, point.device_id, point.signal_id
                    )
                except RegistryError as exc:
                    raise Rejected(str(exc)) from None
                asset_record = next(
                    r
                    for r in self.registry.records()
                    if r.entity.kind == "asset" and r.entity.id == point.asset_id
                )
                assert isinstance(asset_record.entity, Asset)
                asset = asset_record.entity
                if (
                    point.line_id != asset.line_id
                    or point.unit != mapping.input_unit
                    or "telemetry" not in asset.capabilities
                ):
                    raise Rejected("MAPPING_MISMATCH")
                value = point.value * mapping.scale + mapping.offset
                if not 0 <= value <= 100000000:
                    raise Rejected("NORMALIZED_VALUE_INVALID")
                mapping_revision = next(
                    r.revision
                    for r in self.registry.records()
                    if r.entity.kind == "mapping" and r.entity.id == mapping.id
                )
                age = (received - point.event_time).total_seconds()
                flags = []
                if point.quality == "BAD":
                    flags.append("BAD_SOURCE")
                if age > 5:
                    flags.append("STALE")
                if age < -2:
                    flags.append("CLOCK_SKEW")
                # Synthetic fixture plausibility only, never an operational safety bound.
                if value > 10000:
                    flags.append("OUTLIER")
                previous = self.db.execute(
                    "SELECT t.payload FROM latest l JOIN telemetry t ON t.id=l.telemetry_id "
                    "WHERE l.asset_id=?",
                    (point.asset_id,),
                ).fetchone()
                prior = StoredPoint.model_validate_json(previous[0]) if previous else None
                late = prior is not None and (
                    point.sequence <= prior.sequence or point.event_time < prior.event_time
                )
                if late:
                    flags.append("OUT_OF_ORDER")
                cursor = self.db.execute(
                    "INSERT INTO telemetry(idempotency_key,fingerprint,asset_id,"
                    "event_time,sequence,payload) "
                    "VALUES(?,?,?,?,?,?)",
                    (
                        str(point.idempotency_key),
                        fingerprint,
                        point.asset_id,
                        point.event_time.isoformat(),
                        point.sequence,
                        "{}",
                    ),
                )
                assert cursor.lastrowid is not None
                stored = StoredPoint(
                    **{**point.model_dump(), "value": value, "unit": "kW"},
                    received_time=received,
                    flags=flags,
                    row_id=cursor.lastrowid,
                    mapping_id=mapping.id,
                    mapping_revision=mapping_revision,
                )
                self.db.execute(
                    "UPDATE telemetry SET payload=? WHERE id=?",
                    (stored.model_dump_json(), stored.row_id),
                )
                if not late and "CLOCK_SKEW" not in flags:
                    self.db.execute(
                        "INSERT INTO latest VALUES(?,?) ON CONFLICT(asset_id) DO UPDATE "
                        "SET telemetry_id=excluded.telemetry_id",
                        (point.asset_id, stored.row_id),
                    )
                event = TelemetryEvent(
                    event_id=uuid4(),
                    occurred_at=received,
                    org_id=self.org_id,
                    facility_id=self.facility_id,
                    correlation_id=point.idempotency_key,
                    causation_id=point.idempotency_key,
                    idempotency_key=point.idempotency_key,
                    payload=stored,
                )
                self.db.execute(
                    "INSERT INTO outbox VALUES(?,?,?,0)",
                    (stored.row_id, str(event.event_id), event.model_dump_json()),
                )
                accepted += 1
            self.db.execute("UPDATE counters SET value=value+? WHERE name='accepted'", (accepted,))
            self.db.execute(
                "UPDATE counters SET value=value+? WHERE name='duplicates'", (duplicates,)
            )
            if tick is not None:
                self.db.execute("UPDATE identity SET tick=? WHERE singleton=1", (tick,))
        return IngestResult(accepted=accepted, duplicates=duplicates)

    def history(
        self, before: int | None = None, asset: str | None = None, limit: int = 100
    ) -> list[StoredPoint]:
        with self.lock:
            rows = self.db.execute(
                "SELECT payload FROM telemetry WHERE (? IS NULL OR id<?) "
                "AND (? IS NULL OR asset_id=?) ORDER BY id DESC LIMIT ?",
                (before, before, asset, asset, limit),
            ).fetchall()
            return [StoredPoint.model_validate_json(row[0]) for row in rows]

    def state(self) -> tuple[int, list[StoredPoint], dict[str, int], int]:
        with self.lock:
            tick = int(self.db.execute("SELECT tick FROM identity").fetchone()[0])
            points = [
                StoredPoint.model_validate_json(row[0])
                for row in self.db.execute(
                    "SELECT t.payload FROM latest l JOIN telemetry t ON t.id=l.telemetry_id"
                )
            ]
            counts = {str(row[0]): int(row[1]) for row in self.db.execute("SELECT * FROM counters")}
            pending = int(
                self.db.execute("SELECT COUNT(*) FROM outbox WHERE acknowledged=0").fetchone()[0]
            )
            return tick, points, counts, pending

    def events(self, after: int = 0) -> list[TelemetryEvent]:
        with self.lock:
            return [
                TelemetryEvent.model_validate_json(row[0])
                for row in self.db.execute(
                    "SELECT payload FROM outbox WHERE id>? ORDER BY id LIMIT 100", (after,)
                )
            ]
