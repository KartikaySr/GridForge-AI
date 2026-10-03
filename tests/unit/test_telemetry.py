import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from edge.runtime.telemetry import TelemetryRuntime
from edge.storage.repository import CapacityError, Rejected, Repository
from services.telemetry.contracts import TelemetryBatch, TelemetryPoint
from simulator.factory import factory_batch
from tests.support import create_app

NOW = datetime(2026, 9, 22, tzinfo=UTC)


def batch(repo: Repository, tick: int = 1, scenario: str = "normal") -> TelemetryBatch:
    return factory_batch(
        repo.org_id, repo.facility_id, repo.seed, tick, NOW + timedelta(seconds=tick), scenario
    )


def test_deterministic_normalization_and_atomic_outbox(tmp_path: Path) -> None:
    repo = Repository(tmp_path / "edge.db")
    assert batch(repo) == batch(repo)
    incoming = batch(repo)
    assert repo.ingest(incoming, NOW, tick=1).accepted == 5
    assert repo.history()[0].value == incoming.points[-1].value * 0.001
    assert repo.history()[0].unit == "kW"
    assert len(repo.events()) == 5
    assert repo.events()[0].payload.idempotency_key == incoming.points[0].idempotency_key
    assert repo.ingest(incoming, NOW).duplicates == 5
    assert len(repo.events()) == 5
    assert repo.db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    identity = repo.facility_id
    repo.close()
    reopened = Repository(tmp_path / "edge.db")
    assert reopened.facility_id == identity
    assert reopened.state()[0] == 1
    assert reopened.state()[2]["accepted"] == 5
    assert len(reopened.history()) == 5
    reopened.close()


def test_conflicting_replay_and_scope_rollback_entire_batch() -> None:
    repo = Repository(None)
    original = batch(repo)
    repo.ingest(original, NOW)
    different = original.points[0].model_copy(update={"value": 999})
    mixed = TelemetryBatch(points=[batch(repo, 2).points[0], different])
    with pytest.raises(Rejected, match="IDEMPOTENCY_CONFLICT"):
        repo.ingest(mixed, NOW)
    assert len(repo.history()) == len(repo.events()) == 5
    wrong = batch(repo, 3).points[0].model_copy(update={"facility_id": uuid4()})
    with pytest.raises(Rejected, match="SCOPE_MISMATCH"):
        repo.ingest(TelemetryBatch(points=[wrong]), NOW)
    assert repo.state()[2]["accepted"] == 5
    repo.close()


def test_quality_late_and_future_samples_do_not_replace_current_state() -> None:
    repo = Repository(None)
    repo.ingest(batch(repo, 10), NOW + timedelta(seconds=10))
    repo.ingest(batch(repo, 2), NOW + timedelta(seconds=10))
    assert all("OUT_OF_ORDER" in point.flags for point in repo.history(limit=5))
    assert all(point.sequence == 10 for point in repo.state()[1])
    repo.ingest(batch(repo, 30), NOW)
    assert all("CLOCK_SKEW" in point.flags for point in repo.history(limit=5))
    assert all(point.sequence == 10 for point in repo.state()[1])
    repo.ingest(batch(repo, 31, "bad"), NOW + timedelta(seconds=31))
    assert all("BAD_SOURCE" in point.flags for point in repo.state()[1])
    repo.ingest(batch(repo, 70, "stale"), NOW + timedelta(seconds=70))
    assert all("STALE" in point.flags for point in repo.state()[1])
    outlier = batch(repo, 100).points[0].model_copy(update={"value": 20000000, "unit": "W"})
    repo.ingest(TelemetryBatch(points=[outlier]), NOW + timedelta(seconds=100))
    assert "OUTLIER" in repo.history()[0].flags
    repo.close()


@pytest.mark.parametrize(
    "change",
    [
        {"value": float("nan")},
        {"value": float("inf")},
        {"value": -1},
        {"unit": "MW"},
        {"event_time": "2026-09-22T00:00:00"},
        {"asset_id": "invalid space"},
        {"source": "MODBUS"},
        {"sequence": -1},
        {"unknown": "secret"},
    ],
)
def test_invalid_points(change: dict[str, object]) -> None:
    repo = Repository(None)
    data = batch(repo).points[0].model_dump()
    data.update(change)
    with pytest.raises(ValidationError):
        TelemetryPoint.model_validate(data)
    repo.close()


def test_storage_capacity_rejects_atomically_without_evicting_outbox() -> None:
    repo = Repository(None, capacity=7)
    repo.ingest(batch(repo), NOW)
    with pytest.raises(CapacityError, match="STORAGE_FULL"):
        repo.ingest(batch(repo, 2), NOW)
    assert len(repo.history()) == len(repo.events()) == 5
    assert repo.state()[2]["accepted"] == 5
    repo.close()


def test_unknown_migration_version_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "future.db"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=99")
    with pytest.raises(ValueError, match="Unsupported"):
        Repository(path)


def test_bounded_queue_reports_backpressure_and_recovers() -> None:
    async def exercise() -> None:
        engine = TelemetryRuntime(None, simulate=False)
        requests = [asyncio.create_task(engine.submit(batch(engine.repo, i))) for i in range(1, 9)]
        await asyncio.sleep(0)
        assert engine.queue.qsize() == 8
        with pytest.raises(CapacityError, match="QUEUE_FULL"):
            await engine.submit(batch(engine.repo, 9))
        assert engine.repo.state()[2]["backpressure"] == 5
        await engine.start()
        await asyncio.gather(*requests)
        assert engine.queue.empty()
        assert engine.repo.state()[2]["accepted"] == 40
        await engine.close()

    asyncio.run(exercise())


def test_runtime_quality_disconnected_and_recovery_states() -> None:
    engine = TelemetryRuntime(None, simulate=False)
    points = factory_batch(
        engine.repo.org_id, engine.repo.facility_id, 57, 1, datetime.now(UTC), "normal"
    )
    engine.repo.ingest(points, datetime.now(UTC))
    assert all(asset.status == "LIVE" for asset in engine.snapshot().assets)
    engine.scenario = "disconnected"
    assert all(asset.status == "DISCONNECTED" for asset in engine.snapshot().assets)
    engine.scenario = "normal"
    assert all(asset.status == "LIVE" for asset in engine.snapshot().assets)
    engine.failed = True
    assert engine.snapshot().worker_state == "FAILED"
    assert all(asset.status == "DISCONNECTED" for asset in engine.snapshot().assets)
    engine.repo.close()


def test_api_malformed_oversized_scope_and_pagination(tmp_path: Path) -> None:
    token = "a" * 64
    app = create_app(token, uuid4(), tmp_path / "edge.db", simulate=False)
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as client:
        repo = app.state.telemetry.repo
        data = batch(repo).model_dump(mode="json")
        assert client.post("/api/v1/telemetry/batches", json=data).json()["accepted"] == 5
        assert client.post("/api/v1/telemetry/batches", json=data).json()["duplicates"] == 5
        bad = client.post("/api/v1/telemetry/batches", content='{"secret": malformed')
        assert bad.status_code == 422
        assert "secret" not in bad.text
        assert client.post("/api/v1/telemetry/batches", content="x" * 65537).status_code == 413
        assert client.post(
            "/api/v1/telemetry/batches", json={"points": data["points"] * 21}
        ).status_code in (413, 422)
        first = client.get("/api/v1/telemetry?limit=2").json()
        second = client.get(f"/api/v1/telemetry?limit=2&before={first['next_cursor']}").json()
        assert {p["row_id"] for p in first["points"]}.isdisjoint(
            p["row_id"] for p in second["points"]
        )
        assert len(client.get("/api/v1/telemetry?asset=SIM-1").json()["points"]) == 1
        assert len(client.get("/api/v1/telemetry/events?after=2").json()) == 3
        assert (
            client.post("/api/v1/simulator/scenario", json={"scenario": "physical"}).status_code
            == 422
        )
        assert client.get("/api/v1/telemetry?facility_id=other").json()["points"][0][
            "facility_id"
        ] == str(repo.facility_id)
        data["points"][0]["org_id"] = str(uuid4())
        assert client.post("/api/v1/telemetry/batches", json=data).status_code == 409
        assert client.get("/api/v1/telemetry/state").json()["accepted"] == 5


def test_database_failure_stops_new_ingestion_without_false_acknowledgement() -> None:
    async def exercise() -> None:
        engine = TelemetryRuntime(None, simulate=False)
        await engine.start()
        try:
            with patch.object(
                engine.repo, "ingest", side_effect=sqlite3.OperationalError("disk failure")
            ):
                with pytest.raises(CapacityError, match="WORKER_FAILED"):
                    await engine.submit(batch(engine.repo))
            with pytest.raises(CapacityError, match="WORKER_FAILED"):
                await engine.submit(batch(engine.repo, 2))
            assert engine.repo.state()[2]["accepted"] == 0
            assert engine.snapshot().worker_state == "FAILED"
        finally:
            await engine.close()

    asyncio.run(exercise())
