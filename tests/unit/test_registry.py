import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from edge.runtime.telemetry import TelemetryRuntime
from edge.storage.repository import Rejected, Repository
from services.registry.contracts import ENTITY, Asset, Maintenance, RegistryRecord, RegistryWrite
from services.registry.service import RegistryError
from simulator.factory import factory_batch
from tests.support import create_app


def record(repo: Repository, kind: str, identifier: str | None = None) -> RegistryRecord:
    return next(
        r
        for r in repo.registry.records()
        if r.entity.kind == kind and (identifier is None or r.entity.id == identifier)
    )


def edit(repo: Repository, current: RegistryRecord, changes: dict[str, object]) -> RegistryRecord:
    entity = ENTITY.validate_python({**current.entity.model_dump(), **changes})
    return repo.registry.save(
        RegistryWrite(entity=entity, expected_revision=current.revision, request_id=uuid4())
    )


def test_phase2_upgrade_keeps_identity_history_sequence_and_outbox(tmp_path: Path) -> None:
    path = tmp_path / "edge.db"
    repo = Repository(path)
    now = datetime.now(UTC)
    repo.ingest(factory_batch(repo.org_id, repo.facility_id, 57, 40, now, "normal"), now, 40)
    identity = repo.facility_id
    before = repo.history()
    repo.db.executescript(
        "DROP TABLE incidents; DROP TABLE incident_requests; DROP TABLE incident_history; "
        "DROP TABLE incident_cursor; DROP TABLE production_reports; "
        "DROP TABLE sync_conflicts; DROP TABLE sync_streams; DROP TABLE edge_identity; "
        "DROP TABLE finance_outbox; DROP TABLE finance_ledger; "
        "DROP TABLE finance_verifications; DROP TABLE finance_tariffs; "
        "DROP TABLE simulator_commands; DROP TABLE dispatch_requests; "
        "DROP TABLE dispatch_outbox; DROP TABLE dispatch_commands; "
        "DROP TABLE optimization_runs; DROP TABLE optimization_policies; "
        "DROP TABLE optimization_outbox; DROP TABLE forecast_evaluations; "
        "DROP TABLE predictions; DROP TABLE risks; "
        "DROP TABLE model_versions; DROP TABLE intelligence_outbox; DROP INDEX telemetry_time; "
        "DROP TABLE configuration_outbox; DROP TABLE registry; PRAGMA user_version=1;"
    )
    repo.close()
    upgraded = Repository(path)
    assert upgraded.db.execute("PRAGMA user_version").fetchone()[0] == 11
    assert upgraded.facility_id == identity
    assert upgraded.history() == before
    assert upgraded.state()[0] == 40
    assert len(upgraded.events()) == 5
    assert len(upgraded.registry.records()) == len(upgraded.registry.events()) == 15
    upgraded.close()
    reopened = Repository(path)
    assert len(reopened.registry.events()) == 15
    reopened.close()


def test_revision_idempotency_scope_and_transactional_configuration_event() -> None:
    repo = Repository(None)
    current = record(repo, "line")
    write = RegistryWrite(
        entity=current.entity.model_copy(update={"name": "Line A"}),
        expected_revision=1,
        request_id=uuid4(),
    )
    saved = repo.registry.save(write)
    assert saved.revision == 2
    assert repo.registry.save(write) == saved
    assert len(repo.registry.events()) == 16
    assert repo.registry.events()[-1].payload == saved
    assert repo.registry.events(after=15)[0].sequence == 16
    with pytest.raises(RegistryError, match="IDEMPOTENCY_CONFLICT"):
        repo.registry.save(write.model_copy(update={"entity": current.entity}))
    with pytest.raises(RegistryError, match="REVISION_CONFLICT"):
        edit(repo, current, {"name": "Stale edit"})
    with pytest.raises(RegistryError, match="SCOPE_MISMATCH"):
        edit(repo, saved, {"facility_id": uuid4()})
    assert record(repo, "line") == saved
    repo.close()


def test_references_and_disable_order_are_enforced() -> None:
    repo = Repository(None)
    with pytest.raises(RegistryError, match="UNKNOWN_REFERENCE"):
        edit(repo, record(repo, "asset"), {"line_id": "missing-line"})
    with pytest.raises(RegistryError, match="ENABLED_DEPENDENCY"):
        edit(repo, record(repo, "device"), {"enabled": False})
    for item in repo.registry.records():
        if item.entity.kind == "mapping":
            edit(repo, item, {"enabled": False})
    edit(repo, record(repo, "device"), {"enabled": False})
    with pytest.raises(RegistryError, match="ENABLED_DEPENDENCY"):
        edit(repo, record(repo, "mapping"), {"enabled": True})
    repo.close()


@pytest.mark.parametrize(
    "changes",
    [
        {"min_load_kw": 99999},
        {"max_reduction_kw": 100},
        {"rated_kw": float("nan")},
        {"flexible": True},
        {"min_run_seconds": -1},
        {
            "flexible": True,
            "criticality": "CRITICAL",
            "capabilities": ["telemetry", "simulated_load_adjustment"],
        },
    ],
)
def test_invalid_asset_constraints(changes: dict[str, object]) -> None:
    repo = Repository(None)
    with pytest.raises(ValidationError):
        ENTITY.validate_python({**record(repo, "asset").entity.model_dump(), **changes})
    repo.close()


def test_maintenance_blocks_metadata_eligibility_but_not_telemetry() -> None:
    async def exercise() -> None:
        engine = TelemetryRuntime(None, simulate=False)
        current = record(engine.repo, "asset")
        now = datetime.now(UTC)
        saved = edit(
            engine.repo,
            current,
            {
                "flexible": True,
                "max_reduction_kw": 100,
                "capabilities": ["telemetry", "simulated_load_adjustment"],
                "maintenance": [
                    {
                        "starts_at": now - timedelta(hours=1),
                        "ends_at": now + timedelta(hours=1),
                        "reason": "Inspection",
                    }
                ],
            },
        )
        assert isinstance(saved.entity, Asset)
        assert not saved.entity.flexibility_available(now)
        assert saved.entity.flexibility_available(now + timedelta(hours=2))
        batch = engine.adapter.poll(1, now, "normal")
        assert batch is not None and len(batch.points) == 5
        engine.repo.ingest(batch, now, 1)
        assert saved.entity.id not in engine.registry_snapshot().flexibility_available
        await engine.close()

    asyncio.run(exercise())
    with pytest.raises(ValidationError):
        Maintenance(
            starts_at=datetime.now(UTC),
            ends_at=datetime.now(UTC) - timedelta(hours=1),
            reason="Bad window",
        )


def test_mapping_revision_drives_normalization_and_rejects_unmapped_signals() -> None:
    engine = TelemetryRuntime(None, simulate=False)
    now = datetime.now(UTC)
    mapping = record(engine.repo, "mapping", "power-1")
    edit(engine.repo, mapping, {"scale": 0.002, "offset": 1})
    batch = engine.adapter.poll(1, now, "normal")
    assert batch is not None
    raw = next(p for p in batch.points if p.asset_id == "SIM-1")
    engine.repo.ingest(batch, now, 1)
    stored = engine.repo.history(asset="SIM-1")[0]
    assert stored.value == raw.value * 0.002 + 1
    assert stored.mapping_revision == 2
    assert stored.mapping_id == "power-1"
    bad = raw.model_copy(update={"signal_id": "unmapped", "idempotency_key": uuid4()})
    with pytest.raises(Rejected, match="UNMAPPED_SIGNAL"):
        engine.repo.ingest(type(batch)(points=[bad]), now)
    duplicate = mapping.entity.model_copy(update={"id": "duplicate-map"})
    with pytest.raises(RegistryError, match="DUPLICATE_ACTIVE_MAPPING"):
        engine.repo.registry.save(
            RegistryWrite(entity=duplicate, expected_revision=0, request_id=uuid4())
        )
    engine.repo.close()


def test_api_registry_is_authenticated_read_only_ot_and_persistent(tmp_path: Path) -> None:
    path = tmp_path / "edge.db"
    token = "b" * 64
    with TestClient(create_app(token, uuid4(), path, simulate=False)) as client:
        assert client.get("/api/v1/registry").status_code == 401
        client.headers["Authorization"] = f"Bearer {token}"
        data = client.get("/api/v1/registry").json()
        device = next(r for r in data["records"] if r["entity"]["kind"] == "device")
        payload = {
            "entity": {**device["entity"], "writable": True},
            "expected_revision": 1,
            "request_id": str(uuid4()),
        }
        assert client.post("/api/v1/registry", json=payload).status_code == 422
        payload["entity"] = {**device["entity"], "protocol": "MODBUS"}
        assert client.post("/api/v1/registry", json=payload).status_code == 422
        facility = next(r for r in data["records"] if r["entity"]["kind"] == "facility")
        payload["entity"] = {**facility["entity"], "name": "Plant A", "timezone": "Asia/Kolkata"}
        saved = client.post("/api/v1/registry", json=payload)
        assert saved.status_code == 200
        assert client.get("/api/v1/telemetry/state").json()["timezone"] == "Asia/Kolkata"
        assert client.post("/api/v1/dispatch", json={}).status_code == 405
        payload["request_id"] = str(uuid4())
        assert client.post("/api/v1/registry", json=payload).json()["code"] == "REVISION_CONFLICT"
        payload["entity"] = {**facility["entity"], "timezone": "not/a/timezone"}
        assert client.post("/api/v1/registry", json=payload).status_code == 422
    with TestClient(
        create_app(token, uuid4(), path, simulate=False),
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        assert client.get("/api/v1/telemetry/state").json()["facility_name"] == "Plant A"
        assert len(client.get("/api/v1/registry/events?after=15").json()) == 1


def test_configuration_write_rolls_back_if_outbox_fails() -> None:
    repo = Repository(None)
    current = record(repo, "line")
    repo.db.executescript(
        "CREATE TRIGGER fail_event BEFORE INSERT ON configuration_outbox "
        "BEGIN SELECT RAISE(ABORT,'test failure'); END;"
    )
    with pytest.raises(sqlite3.IntegrityError):
        edit(repo, current, {"name": "Must roll back"})
    assert record(repo, "line") == current
    repo.close()


def test_new_registry_hierarchy_drives_adapter_and_disable_health() -> None:
    from services.registry.contracts import Device, ProductionLine, RegistryEntity, SignalMapping

    engine = TelemetryRuntime(None, simulate=False)
    repo = engine.repo
    entities: list[RegistryEntity] = [
        ProductionLine(
            id="test-line", name="Test line", org_id=repo.org_id, facility_id=repo.facility_id
        ),
        Asset(
            id="test-asset",
            name="Test asset",
            line_id="test-line",
            rated_kw=100,
            max_load_kw=200,
            org_id=repo.org_id,
            facility_id=repo.facility_id,
        ),
        Device(
            id="test-device", name="Test device", org_id=repo.org_id, facility_id=repo.facility_id
        ),
        SignalMapping(
            id="test-map",
            name="Test mapping",
            asset_id="test-asset",
            device_id="test-device",
            signal_id="power",
            org_id=repo.org_id,
            facility_id=repo.facility_id,
        ),
    ]
    for entity in entities:
        repo.registry.save(RegistryWrite(entity=entity, expected_revision=0, request_id=uuid4()))
    now = datetime.now(UTC)
    batch = engine.adapter.poll(1, now, "normal")
    assert batch is not None and len(batch.points) == 6
    assert batch == engine.adapter.poll(1, now, "normal")
    repo.ingest(batch, now, 1)
    assert repo.history(asset="test-asset")[0].mapping_id == "test-map"
    assert (
        next(c for c in engine.registry_snapshot().connectors if c.device_id == "test-device").state
        == "CONNECTED"
    )
    edit(repo, record(repo, "mapping", "test-map"), {"enabled": False})
    edit(repo, record(repo, "device", "test-device"), {"enabled": False})
    assert (
        next(c for c in engine.registry_snapshot().connectors if c.device_id == "test-device").state
        == "DISABLED"
    )
    assert (
        next(a for a in engine.snapshot().assets if a.asset_id == "test-asset").status
        == "DISCONNECTED"
    )
    repo.close()
