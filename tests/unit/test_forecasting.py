import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from edge.storage.repository import Repository
from services.forecasting.contracts import ModelVersion
from services.forecasting.features import features
from services.forecasting.service import ForecastService
from services.registry.contracts import Facility, RegistryWrite
from services.telemetry.contracts import StoredPoint
from simulator.factory import factory_batch
from tests.support import create_app

ORIGIN = datetime(2026, 9, 23, 10, tzinfo=UTC)


def test_real_ingestion_normalization_to_forecast_and_risk() -> None:
    repo = Repository(None)
    service = ForecastService(repo)
    threshold(repo, 100)
    for second in range(300):
        at = ORIGIN - timedelta(seconds=300 - second)
        batch = factory_batch(repo.org_id, repo.facility_id, 57, second + 1, at, "normal")
        repo.ingest(batch, at, second + 1)
    prediction = service.run(ORIGIN)
    assert prediction.status == "READY"
    assert prediction.evidence.row_count == 1500
    assert service.snapshot(now=ORIGIN).risk_assessment == "BREACH"
    assert len(service.risks()) == 1
    assert len(service.events()) == 2
    assert repo.state()[2]["accepted"] == 1500
    repo.close()


def threshold(repo: Repository, value: float | None) -> None:
    current = next(r for r in repo.registry.records() if isinstance(r.entity, Facility))
    repo.registry.save(
        RegistryWrite(
            entity=current.entity.model_copy(update={"simulation_demand_threshold_kw": value}),
            expected_revision=current.revision,
            request_id=uuid4(),
        )
    )


def seed(
    repo: Repository, start: datetime, minutes: int, kw: float = 100, quality: str = "GOOD"
) -> None:
    """Bulk normalized fixture for long chronological tests; API ingestion tested separately."""
    with repo.lock, repo.db:
        row_id = repo.db.execute("SELECT COALESCE(MAX(id),0) FROM telemetry").fetchone()[0]
        for minute_index in range(minutes):
            for second in range(60):
                at = start + timedelta(minutes=minute_index, seconds=second)
                for asset in range(1, 6):
                    row_id += 1
                    p = StoredPoint.model_validate(
                        dict(
                            org_id=repo.org_id,
                            facility_id=repo.facility_id,
                            asset_id=f"SIM-{asset}",
                            value=kw,
                            unit="kW",
                            quality=quality,
                            event_time=at,
                            received_time=at,
                            sequence=row_id,
                            idempotency_key=uuid4(),
                            row_id=row_id,
                            flags=[] if quality == "GOOD" else ["BAD_SOURCE"],
                            mapping_id=f"power-{asset}",
                            mapping_revision=1,
                        )
                    )
                    repo.db.execute(
                        "INSERT INTO telemetry VALUES (?,?,?,?,?,?,?)",
                        (
                            row_id,
                            str(p.idempotency_key),
                            "fixture",
                            p.asset_id,
                            at.isoformat(),
                            row_id,
                            p.model_dump_json(),
                        ),
                    )
                    repo.db.execute(
                        "INSERT INTO latest VALUES (?,?) ON CONFLICT(asset_id) DO UPDATE "
                        "SET telemetry_id=excluded.telemetry_id",
                        (p.asset_id, row_id),
                    )


def test_baseline_provenance_and_no_future_or_late_backfill_leakage() -> None:
    repo = Repository(None)
    service = ForecastService(repo)
    seed(repo, ORIGIN - timedelta(minutes=5), 5)
    prediction = service.run(ORIGIN)
    assert prediction.status == "READY"
    assert len(prediction.values) == 30
    assert all(p.value_kw == 500 for p in prediction.values)
    assert prediction.values[-1].ends_at == ORIGIN + timedelta(minutes=30)
    assert prediction.confidence is None
    assert prediction.evidence.row_count == 1500
    rows = service.points(ORIGIN - timedelta(minutes=5), ORIGIN)
    backfill = rows[0].model_copy(
        update={"value": 9999, "received_time": ORIGIN + timedelta(seconds=1)}
    )
    future = rows[0].model_copy(update={"value": 9999, "event_time": ORIGIN + timedelta(seconds=1)})
    original = prediction.evidence
    computed = features(
        rows + [backfill, future],
        original.window_start,
        5,
        ORIGIN,
        original.asset_ids,
        original.mapping_revisions,
        original.registry_digest,
    )
    assert computed == original
    assert service.run(ORIGIN + timedelta(seconds=1)) == prediction
    assert len(service.events()) == 1
    repo.close()


@pytest.mark.parametrize(
    "case", ["empty", "bad", "stale", "disconnected", "missing", "duplicate_seconds"]
)
def test_degraded_inputs_never_produce_numbers(case: str) -> None:
    repo = Repository(None)
    service = ForecastService(repo)
    if case != "empty":
        seed(repo, ORIGIN - timedelta(minutes=5), 5, quality="BAD" if case == "bad" else "GOOD")
    if case == "missing":
        repo.db.execute("DELETE FROM latest WHERE asset_id='SIM-1'")
    if case == "duplicate_seconds":
        with repo.db:
            repo.db.execute("DELETE FROM latest")
            repo.db.execute(
                "DELETE FROM telemetry WHERE CAST(strftime('%S',event_time) AS INTEGER)<48"
            )
            repo.db.execute(
                "INSERT INTO latest SELECT asset_id,MAX(id) FROM telemetry GROUP BY asset_id"
            )
    result = service.run(
        ORIGIN + timedelta(seconds=10) if case == "stale" else ORIGIN,
        disconnected=case == "disconnected",
    )
    assert result.status == "DEGRADED"
    assert result.values == []
    assert service.snapshot(now=ORIGIN).risk_assessment == "UNKNOWN"
    repo.close()


def test_time_based_evaluation_waits_for_horizon_and_records_real_errors() -> None:
    repo = Repository(None)
    service = ForecastService(repo)
    threshold(repo, 550)
    seed(repo, ORIGIN - timedelta(minutes=5), 5)
    predicted = service.run(ORIGIN)
    assert service.evaluate_due(ORIGIN + timedelta(minutes=30)) is None
    seed(repo, ORIGIN, 30, kw=120)
    result = service.evaluate_due(ORIGIN + timedelta(minutes=30, seconds=5))
    assert result is not None and result.status == "EVALUATED"
    assert result.prediction_id == predicted.id
    assert result.mae_kw == result.rmse_kw == 100
    assert result.mape_percent == pytest.approx(100 / 6)
    assert result.peak_predicted is False and result.peak_actual is True
    assert result.actual_evidence.window_start == predicted.as_of
    assert service.summary().peak_recall == 0
    assert service.summary().peak_precision is None
    assert service.evaluate_due(ORIGIN + timedelta(minutes=31)) is None
    assert len(service.events()) == 2
    repo.close()


def test_missing_future_actuals_record_unknown_not_zero_error() -> None:
    repo = Repository(None)
    service = ForecastService(repo)
    seed(repo, ORIGIN - timedelta(minutes=5), 5)
    service.run(ORIGIN)
    result = service.evaluate_due(ORIGIN + timedelta(minutes=31))
    assert result and result.status == "UNKNOWN" and result.mae_kw is None
    assert service.summary().unknown_predictions == 1
    repo.close()


def test_risk_detection_degradation_resolution_supersession_and_restart(tmp_path: Path) -> None:
    path = tmp_path / "risk.db"
    repo = Repository(path)
    service = ForecastService(repo)
    threshold(repo, 450)
    seed(repo, ORIGIN - timedelta(minutes=5), 5)
    first = service.run(ORIGIN)
    assert service.snapshot(now=ORIGIN).risk_assessment == "BREACH"
    assert service.risks()[0].first_prediction_id == first.id
    service.run(ORIGIN + timedelta(seconds=6), disconnected=True)
    assert service.snapshot(disconnected=True, now=ORIGIN).risk_assessment == "UNKNOWN"
    assert service.risks()[0].state == "OPEN"
    seed(repo, ORIGIN, 5, kw=50)
    clear = service.run(ORIGIN + timedelta(minutes=5))
    assert clear.status == "READY"
    assert service.risks()[0].state == "RESOLVED"
    seed(repo, ORIGIN + timedelta(minutes=5), 5)
    service.run(ORIGIN + timedelta(minutes=10))
    threshold(repo, None)
    service.run(ORIGIN + timedelta(minutes=10, seconds=1))
    assert {r.state for r in service.risks()} == {"RESOLVED", "SUPERSEDED"}
    events = service.events()
    assert {e.event_type for e in events} >= {
        "RiskDetected",
        "RiskResolved",
        "RiskSuperseded",
        "ForecastFailed",
    }
    before = service.history()
    repo.close()
    reopened = Repository(path)
    assert ForecastService(reopened).history() == before
    assert ForecastService(reopened).events() == events
    reopened.close()


def test_mapping_change_invalidates_current_and_historical_coverage() -> None:
    repo = Repository(None)
    service = ForecastService(repo)
    seed(repo, ORIGIN - timedelta(minutes=5), 5)
    service.run(ORIGIN)
    mapping = next(r for r in repo.registry.records() if r.entity.id == "power-1")
    repo.registry.save(
        RegistryWrite(
            entity=mapping.entity.model_copy(update={"scale": 0.002}),
            expected_revision=1,
            request_id=uuid4(),
        )
    )
    assert service.snapshot(now=ORIGIN).status == "DEGRADED"
    assert service.run(ORIGIN).values == []
    repo.close()


def test_atomic_outbox_failure_and_capacity_preserve_existing_evidence() -> None:
    repo = Repository(None)
    service = ForecastService(repo)
    origin = datetime.now(UTC).replace(second=0, microsecond=0) - timedelta(hours=1)
    seed(repo, origin - timedelta(minutes=5), 5)
    repo.db.executescript(
        "CREATE TRIGGER fail_forecast BEFORE INSERT ON intelligence_outbox "
        "BEGIN SELECT RAISE(ABORT,'test'); END;"
    )
    with pytest.raises(sqlite3.IntegrityError):
        service.run(origin)
    assert service.history() == []
    repo.db.execute("DROP TRIGGER fail_forecast")
    service.run(origin)
    service.capacity = 1
    with pytest.raises(ValueError, match="CAPACITY"):
        service.run(origin + timedelta(minutes=1))
    assert len(service.history()) == 1
    service.tick()
    assert service.worker_error == "INFERENCE_OR_STORAGE_FAILED"
    assert service.summary().unknown_predictions == 1
    repo.close()


def test_phase3_upgrade_and_model_immutability(tmp_path: Path) -> None:
    path = tmp_path / "phase3.db"
    repo = Repository(path)
    identity = repo.facility_id
    seed(repo, ORIGIN - timedelta(minutes=5), 5)
    before = repo.history()
    repo.db.executescript(
        "DROP TABLE sync_conflicts; DROP TABLE sync_streams; DROP TABLE edge_identity; "
        "DROP TABLE finance_outbox; DROP TABLE finance_ledger; "
        "DROP TABLE finance_verifications; DROP TABLE finance_tariffs; "
        "DROP TABLE simulator_commands; DROP TABLE dispatch_requests; "
        "DROP TABLE dispatch_outbox; DROP TABLE dispatch_commands; "
        "DROP TABLE optimization_runs; DROP TABLE optimization_policies; "
        "DROP TABLE optimization_outbox; DROP TABLE forecast_evaluations; "
        "DROP TABLE predictions; DROP TABLE risks; "
        "DROP TABLE model_versions; DROP TABLE intelligence_outbox; "
        "DROP INDEX telemetry_time; PRAGMA user_version=2;"
    )
    repo.close()
    repo = Repository(path)
    assert repo.db.execute("PRAGMA user_version").fetchone()[0] == 9
    assert repo.facility_id == identity and repo.history() == before
    ForecastService(repo)
    with repo.db:
        repo.db.execute(
            "UPDATE model_versions SET body=?",
            (ModelVersion(history_minutes=99).model_dump_json(),),
        )
    with pytest.raises(ValueError, match="Immutable"):
        ForecastService(repo)
    repo.close()


def test_native_api_scope_auth_and_worker_warmup() -> None:
    app = create_app("c" * 64, uuid4(), simulate=False)
    with TestClient(app) as client:
        assert client.get("/api/v1/intelligence").status_code == 401
        client.headers["Authorization"] = "Bearer " + "c" * 64
        snapshot = client.get("/api/v1/intelligence")
        assert snapshot.status_code == 200
        assert snapshot.json()["status"] == "DEGRADED"
        assert snapshot.json()["risk_assessment"] == "UNKNOWN"
        assert (
            client.get(
                "/api/v1/intelligence", headers={"Origin": "https://bad.example"}
            ).status_code
            == 401
        )
        assert client.get("/api/v1/forecasts?before=0").status_code == 422
        assert client.get("/api/v1/intelligence/events?after=0").status_code == 200
        assert client.post("/api/v1/forecasts", json={}).status_code == 405
