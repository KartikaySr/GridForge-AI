from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from edge.storage.repository import CapacityError, Rejected, Repository
from services.forecasting.service import ForecastService
from services.optimization.contracts import PolicyInput, PolicyWrite, RunRequest
from services.optimization.engine import evaluate
from services.optimization.service import OptimizationService
from services.registry.contracts import Asset, Maintenance, RegistryWrite
from tests.support import create_app
from tests.unit.test_forecasting import ORIGIN, seed, threshold


def setup(path: Path | None = None) -> tuple[Repository, OptimizationService, RunRequest]:
    repo = Repository(path)
    threshold(repo, 450)
    record = next(r for r in repo.registry.records() if r.entity.id == "SIM-1")
    asset = Asset.model_validate(
        record.entity.model_dump()
        | dict(
            flexible=True,
            capabilities=["telemetry", "simulated_load_adjustment"],
            max_reduction_kw=80,
        )
    )
    repo.registry.save(
        RegistryWrite(request_id=uuid4(), expected_revision=record.revision, entity=asset)
    )
    seed(repo, ORIGIN - timedelta(minutes=5), 5)
    forecasting = ForecastService(repo)
    forecasting.run(ORIGIN)
    service = OptimizationService(repo, forecasting)
    policy = service.save_policy(
        PolicyWrite(
            request_id=uuid4(),
            policy=PolicyInput(
                name="test",
                effective_from=ORIGIN - timedelta(minutes=1),
                effective_until=ORIGIN + timedelta(hours=1),
                max_duration_seconds=600,
                max_total_reduction_kw=100,
                simulation_rate_per_kwh=Decimal("0.12"),
            ),
        ),
        ORIGIN,
    )
    return repo, service, RunRequest(request_id=uuid4(), policy_id=policy.id, duration_seconds=300)


def test_complete_proposal_money_and_replay_survive_restart(tmp_path: Path) -> None:
    path = tmp_path / "edge.db"
    repo, service, request = setup(path)
    run = service.run(request, now=ORIGIN)
    assert run.status == "PROPOSED"
    assert run.proposal and run.proposal.expected_reduction_kw == 50
    assert run.proposal.economic_estimate.amount == Decimal("0.50")
    assert run.proposal.authorization == "NOT_AUTHORIZED"
    assert len(run.candidates) == 5
    assert sum(c.selected_kw for c in run.candidates) == 50
    assert all(c.selected_kw == 0 for c in run.candidates if not c.eligible)
    assert run.prediction_id and run.risk_ids and run.registry_digest
    assert service.snapshot(now=ORIGIN).latest_is_current
    assert not service.snapshot(now=ORIGIN + timedelta(seconds=6)).latest_is_current
    assert service.run(request, now=ORIGIN + timedelta(hours=1)) == run
    assert len(service.events()) == 3
    repo.close()
    repo = Repository(path)
    service = OptimizationService(repo, ForecastService(repo))
    assert service.run(request, now=ORIGIN) == run
    assert service.history()[0] == run
    assert service.events(1)[0].event_type == "OptimizationStarted"
    with pytest.raises(Rejected, match="IDEMPOTENCY_CONFLICT"):
        service.run(request.model_copy(update={"duration_seconds": 60}), now=ORIGIN)
    repo.close()


@pytest.mark.parametrize(
    "change,code",
    [
        ({"enabled": False}, "ENABLED"),
        ({"criticality": "CRITICAL", "flexible": False, "max_reduction_kw": 0}, "NONCRITICAL"),
        ({"flexible": False, "max_reduction_kw": 0}, "SIMULATED_CAPABILITY"),
        ({"min_run_seconds": 1}, "RUNTIME_DOWNTIME_EVIDENCE"),
        ({"min_off_seconds": 1}, "RUNTIME_DOWNTIME_EVIDENCE"),
        ({"min_load_kw": 110}, "LOAD_BOUNDS"),
        (
            {
                "maintenance": [
                    Maintenance(
                        starts_at=ORIGIN + timedelta(seconds=30),
                        ends_at=ORIGIN + timedelta(seconds=90),
                        reason="planned",
                    )
                ]
            },
            "MAINTENANCE",
        ),
    ],
)
def test_hard_constraints_reject_even_with_best_soft_score(
    change: dict[str, object], code: str
) -> None:
    repo, service, request = setup()
    records = repo.registry.records()
    asset = next(r.entity for r in records if r.entity.id == "SIM-1")
    assert isinstance(asset, Asset)
    policy = (
        service.snapshot(now=ORIGIN)
        .policies[0]
        .model_copy(update={"asset_penalties": {"SIM-1": 0}})
    )
    point = next(p for p in repo.state()[1] if p.asset_id == asset.id)
    candidate = evaluate(
        asset.model_copy(update=change),
        records,
        point,
        policy,
        ORIGIN,
        ORIGIN + timedelta(seconds=request.duration_seconds),
    )
    assert not candidate.eligible
    assert not next(c for c in candidate.constraints if c.code == code).passed
    assert candidate.selected_kw == 0
    repo.close()


@pytest.mark.parametrize(
    "condition",
    [
        "disconnected",
        "stale",
        "expired_policy",
        "duration",
        "cap",
        "missing_threshold",
        "config_changed",
        "bad",
        "missing",
    ],
)
def test_fail_closed(condition: str) -> None:
    repo, service, request = setup()
    now = ORIGIN
    if condition == "stale":
        now += timedelta(seconds=70)
    if condition in ("expired_policy", "cap"):
        policy = service.snapshot(now=ORIGIN).policies[0]
        values = policy.model_dump(include=set(PolicyInput.model_fields))
        values.update(
            {"effective_until": ORIGIN}
            if condition == "expired_policy"
            else {"max_total_reduction_kw": 10}
        )
        saved = service.save_policy(
            PolicyWrite(request_id=uuid4(), policy=PolicyInput.model_validate(values)), ORIGIN
        )
        request = request.model_copy(update={"policy_id": saved.id})
    if condition == "duration":
        request = request.model_copy(update={"duration_seconds": 900})
    if condition == "missing_threshold":
        threshold(repo, None)
    if condition == "config_changed":
        threshold(repo, 449)
    if condition in ("bad", "missing"):
        with repo.db:
            if condition == "missing":
                repo.db.execute("DELETE FROM latest WHERE asset_id='SIM-1'")
            else:
                row = repo.db.execute(
                    "SELECT telemetry_id FROM latest WHERE asset_id='SIM-1'"
                ).fetchone()[0]
                repo.db.execute(
                    "UPDATE telemetry SET payload=json_set(payload,'$.quality','BAD') WHERE id=?",
                    (row,),
                )
    result = service.run(request, disconnected=condition == "disconnected", now=now)
    assert result.status == "INFEASIBLE"
    assert result.proposal is None
    assert all(c.selected_kw == 0 for c in result.candidates)
    repo.close()


def test_missing_rate_no_action_capacity_and_atomicity(monkeypatch: pytest.MonkeyPatch) -> None:
    repo, service, request = setup()
    p = service.snapshot(now=ORIGIN).policies[0]
    write = PolicyWrite(
        request_id=uuid4(),
        policy=PolicyInput.model_validate(
            p.model_dump(include=set(PolicyInput.model_fields)) | {"simulation_rate_per_kwh": None}
        ),
    )
    saved = service.save_policy(write, ORIGIN)
    assert service.save_policy(write, ORIGIN) == saved
    with pytest.raises(Rejected):
        service.save_policy(
            write.model_copy(
                update={"policy": write.policy.model_copy(update={"name": "changed"})}
            ),
            ORIGIN,
        )
    result = service.run(request.model_copy(update={"policy_id": saved.id}), now=ORIGIN)
    assert result.proposal and result.proposal.economic_estimate.amount is None
    assert result.proposal.economic_estimate.status == "INCOMPLETE"
    threshold(repo, 600)
    service.forecasting.run(ORIGIN)
    result = service.run(request.model_copy(update={"request_id": uuid4()}), now=ORIGIN)
    assert result.status == "NO_ACTION" and result.proposal is None
    before = len(service.events())

    def fail(*args: object) -> None:
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr(service, "emit", fail)
    with pytest.raises(RuntimeError):
        service.run(request.model_copy(update={"request_id": uuid4()}), now=ORIGIN)
    assert service.snapshot(now=ORIGIN).run_count == 2 and len(service.events()) == before
    service.capacity = 2
    with pytest.raises(CapacityError):
        service.run(request.model_copy(update={"request_id": uuid4()}), now=ORIGIN)
    repo.close()


def test_api_auth_scope_and_extra_command_fields(tmp_path: Path) -> None:
    with TestClient(create_app("a" * 64, uuid4(), tmp_path / "edge.db", simulate=False)) as client:
        headers = {"Authorization": "Bearer " + "a" * 64}
        assert client.get("/api/v1/optimization").status_code == 401
        assert (
            client.get(
                "/api/v1/optimization", headers=headers | {"Origin": "http://evil"}
            ).status_code
            == 401
        )
        assert client.get("/api/v1/optimization", headers=headers).json()["latest"] is None
        body = dict(request_id=str(uuid4()), policy_id=str(uuid4()), duration_seconds=60)
        assert (
            client.post("/api/v1/optimization/runs", headers=headers, json=body).status_code == 409
        )
        assert (
            client.post(
                "/api/v1/optimization/runs",
                headers=headers,
                json=body | {"facility_id": str(uuid4())},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/optimization/runs",
                headers=headers,
                json=body | {"override_constraints": True},
            ).status_code
            == 422
        )


def test_phase4_upgrade_preserves_records(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    repo = Repository(path)
    original = repo.registry.records()
    repo.db.executescript(
        "DROP TABLE sync_conflicts; DROP TABLE sync_streams; DROP TABLE edge_identity; "
        "DROP TABLE finance_outbox; DROP TABLE finance_ledger; "
        "DROP TABLE finance_verifications; DROP TABLE finance_tariffs; "
        "DROP TABLE simulator_commands; DROP TABLE dispatch_requests; "
        "DROP TABLE dispatch_outbox; DROP TABLE dispatch_commands; "
        "DROP TABLE optimization_runs; DROP TABLE optimization_policies; "
        "DROP TABLE optimization_outbox; PRAGMA user_version=3;"
    )
    repo.close()
    repo = Repository(path)
    assert repo.registry.records() == original
    assert repo.db.execute("PRAGMA user_version").fetchone()[0] == 9
    repo.close()


def test_real_simulator_ingestion_to_proposal() -> None:
    from simulator.factory import factory_batch

    repo = Repository(None)
    threshold(repo, 4400)
    for record in repo.registry.records():
        if isinstance(record.entity, Asset) and record.entity.id != "SIM-5":
            asset = Asset.model_validate(
                record.entity.model_dump()
                | dict(
                    flexible=True,
                    capabilities=["telemetry", "simulated_load_adjustment"],
                    max_reduction_kw=record.entity.rated_kw / 2,
                )
            )
            repo.registry.save(
                RegistryWrite(request_id=uuid4(), expected_revision=record.revision, entity=asset)
            )
    for second in range(300):
        at = ORIGIN - timedelta(seconds=300 - second)
        repo.ingest(factory_batch(repo.org_id, repo.facility_id, 57, second + 1, at, "normal"), at)
    forecasting = ForecastService(repo)
    forecasting.run(ORIGIN)
    service = OptimizationService(repo, forecasting)
    policy = service.save_policy(
        PolicyWrite(
            request_id=uuid4(),
            policy=PolicyInput(
                name="Actual adapter evidence",
                effective_from=ORIGIN,
                effective_until=ORIGIN + timedelta(hours=1),
                max_duration_seconds=300,
                max_total_reduction_kw=2000,
                asset_penalties={"SIM-1": 10, "SIM-2": 0},
            ),
        ),
        ORIGIN,
    )
    run = service.run(
        RunRequest(request_id=uuid4(), policy_id=policy.id, duration_seconds=300), now=ORIGIN
    )
    assert run.status == "PROPOSED"
    assert next(c for c in run.candidates if c.asset_id == "SIM-5").eligible is False
    assert next(c for c in run.candidates if c.asset_id == "SIM-2").selected_kw > 0
    assert all(c.selected_kw <= c.available_kw for c in run.candidates)
    assert sum(c.selected_kw for c in run.candidates) == pytest.approx(run.required_reduction_kw)
    repo.close()


def test_device_mapping_and_quality_gates() -> None:
    repo, service, _ = setup()
    records = repo.registry.records()
    asset = next(r.entity for r in records if r.entity.id == "SIM-1")
    assert isinstance(asset, Asset)
    policy = service.snapshot(now=ORIGIN).policies[0]
    point = next(p for p in repo.state()[1] if p.asset_id == asset.id)
    cases = [
        (records, None, "LIVE_QUALITY"),
        (records, point.model_copy(update={"mapping_revision": 99}), "MAPPING_REVISION"),
        (
            records,
            point.model_copy(update={"event_time": ORIGIN + timedelta(seconds=1)}),
            "LIVE_QUALITY",
        ),
        (records, point.model_copy(update={"flags": ["OUTLIER"]}), "LIVE_QUALITY"),
        ([r for r in records if r.entity.kind != "device"], point, "MAPPING_DEVICE"),
        ([r for r in records if r.entity.id != "power-1"], point, "MAPPING_DEVICE"),
    ]
    for context, evidence, code in cases:
        candidate = evaluate(
            asset, context, evidence, policy, ORIGIN, ORIGIN + timedelta(seconds=60)
        )
        assert not candidate.eligible
        assert not next(c for c in candidate.constraints if c.code == code).passed
    repo.close()
