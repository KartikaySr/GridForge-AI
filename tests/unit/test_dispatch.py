from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from edge.connectors.simulator import SimulatorAdapter
from edge.storage.repository import Rejected, Repository
from services.dispatch.contracts import ApprovalRequest, DecisionRequest, DispatchCommand
from services.dispatch.permissions import SIMULATION_PERMISSIONS, PermissionDenied, Principal
from services.dispatch.service import DispatchService
from services.forecasting.service import ForecastService
from simulator.factory import factory_batch
from tests.support import create_app
from tests.unit.test_forecasting import ORIGIN, threshold
from tests.unit.test_optimization import setup


def fixture(
    behavior: Literal["normal", "delayed_ack", "missing_ack", "failed_command"] = "normal",
) -> tuple[Repository, DispatchService, Principal, ApprovalRequest]:
    repo, optimization, request = setup()
    run = optimization.run(request, now=ORIGIN)
    assert run.proposal
    service = DispatchService(repo, ForecastService(repo))
    principal = Principal(
        actor="human-local-simulation",
        org_id=repo.org_id,
        facility_id=repo.facility_id,
        permissions=SIMULATION_PERMISSIONS,
        expires_at=ORIGIN + timedelta(hours=1),
    )
    approval = ApprovalRequest(request_id=uuid4(), run_id=run.id, behavior=behavior)
    return repo, service, principal, approval


def decide(
    service: DispatchService,
    principal: Principal,
    command_id: UUID,
    revision: int,
    action: Literal["approve", "reject", "cancel"],
    now: datetime,
    request_id: UUID | None = None,
) -> DispatchCommand:
    write = DecisionRequest(
        request_id=request_id or uuid4(),
        command_id=command_id,
        expected_revision=revision,
        action=action,
        reason="Human reviewed simulated command",
    )
    return service.decide(write, principal, now=now)


def ingest_next(repo: Repository, second: int) -> None:
    at = ORIGIN + timedelta(seconds=second)
    repo.ingest(factory_batch(repo.org_id, repo.facility_id, 57, 2000 + second, at, "normal"), at)


def test_human_approval_ack_effect_cancel_and_replay() -> None:
    repo, service, principal, approval = fixture()
    command = service.request(approval, principal, now=ORIGIN)
    assert command.state == "PENDING_APPROVAL"
    assert service.request(approval, principal, now=ORIGIN) == command
    with pytest.raises(Rejected, match="IDEMPOTENCY_CONFLICT"):
        service.request(
            approval.model_copy(update={"behavior": "missing_ack"}), principal, now=ORIGIN
        )
    with pytest.raises(Rejected, match="PROPOSAL_ALREADY_REQUESTED"):
        service.request(approval.model_copy(update={"request_id": uuid4()}), principal, now=ORIGIN)
    result = decide(service, principal, command.id, command.revision, "approve", ORIGIN)
    assert result.state == "QUEUED" and result.approved_by == principal.actor
    service.tick(now=ORIGIN + timedelta(seconds=0.2))
    assert service.load(command.id).state == "SENT"
    service.tick(now=ORIGIN + timedelta(seconds=1.3))
    assert service.load(command.id).state == "ACKNOWLEDGED"
    service.tick(now=ORIGIN + timedelta(seconds=1.6))
    assert service.load(command.id).state == "EXECUTING"
    adapter = SimulatorAdapter(repo.registry)
    before = adapter.poll(303, ORIGIN + timedelta(seconds=2), "normal")
    assert before and before.points
    # Active adapter reduction is included in generated telemetry. Base profile is deterministic.
    active = next(p for p in before.points if p.asset_id == "SIM-1")
    row = repo.db.execute(
        "SELECT active FROM simulator_commands WHERE command_id=?", (str(command.id),)
    ).fetchone()
    assert row[0] == 1
    assert active.value < 920000
    cancelled = decide(
        service,
        principal,
        command.id,
        service.load(command.id).revision,
        "cancel",
        ORIGIN + timedelta(seconds=2),
    )
    assert cancelled.state == "CANCELLED"
    after = adapter.poll(303, ORIGIN + timedelta(seconds=2), "normal")
    assert after
    restored = next(p for p in after.points if p.asset_id == "SIM-1")
    assert restored.value - active.value == pytest.approx(50000, abs=0.01)
    assert (
        repo.db.execute(
            "SELECT active FROM simulator_commands WHERE command_id=?", (str(command.id),)
        ).fetchone()[0]
        == 0
    )
    assert [e.event_type for e in service.detail(command.id, principal, ORIGIN).timeline] == [
        "ApprovalRequested",
        "ApprovalGranted",
        "DispatchQueued",
        "DispatchSent",
        "DispatchAcknowledged",
        "DispatchExecuting",
        "DispatchCancelled",
    ]
    repo.close()


@pytest.mark.parametrize(
    "behavior,outcome",
    [
        ("failed_command", "SIMULATOR_COMMAND_REJECTED"),
        ("missing_ack", "ACK_TIMEOUT"),
        ("delayed_ack", "EXECUTING"),
    ],
)
def test_ack_retry_and_failure(
    behavior: Literal["normal", "delayed_ack", "missing_ack", "failed_command"], outcome: str
) -> None:
    repo, service, principal, approval = fixture(behavior)
    command = service.request(approval, principal, now=ORIGIN)
    decide(service, principal, command.id, command.revision, "approve", ORIGIN)
    service.tick(now=ORIGIN + timedelta(seconds=0.1))
    for second in range(1, 12):
        ingest_next(repo, second)
        service.tick(now=ORIGIN + timedelta(seconds=second + 0.1))
        if service.load(command.id).state in ("FAILED", "EXECUTING"):
            break
    state = service.load(command.id)
    assert (state.reason if outcome != "EXECUTING" else state.state).startswith(outcome)
    assert state.attempts == (1 if behavior == "failed_command" else 2)
    assert sum(
        e.event_type == "DispatchRetried"
        for e in service.detail(command.id, principal, ORIGIN).timeline
    ) == (0 if behavior == "failed_command" else 1)
    if behavior == "missing_ack":
        assert state.state == "FAILED" and state.execution_started_at is None
    repo.close()


def test_approval_timeout_rejection_cancel_and_restart(tmp_path: Path) -> None:
    path = tmp_path / "edge.db"
    repo, opt, request = setup(path)
    run = opt.run(request, now=ORIGIN)
    service = DispatchService(repo, ForecastService(repo))
    principal = Principal(
        "human", repo.org_id, repo.facility_id, SIMULATION_PERMISSIONS, ORIGIN + timedelta(hours=1)
    )
    command = service.request(
        ApprovalRequest(request_id=uuid4(), run_id=run.id), principal, now=ORIGIN
    )
    service.tick(now=ORIGIN + timedelta(seconds=121))
    assert service.load(command.id).state == "REJECTED"
    assert service.load(command.id).reason == "APPROVAL_TIMEOUT"
    assert not repo.db.execute("SELECT 1 FROM simulator_commands").fetchone()
    repo.close()
    repo = Repository(path)
    service = DispatchService(repo, ForecastService(repo))
    assert service.load(command.id).state == "REJECTED"
    assert not service.active()
    repo.close()


def test_recovery_fails_active_command_and_prevents_response() -> None:
    repo, service, principal, approval = fixture()
    command = service.request(approval, principal, now=ORIGIN)
    decide(service, principal, command.id, command.revision, "approve", ORIGIN)
    service.tick(now=ORIGIN + timedelta(seconds=0.1))
    service.tick(now=ORIGIN + timedelta(seconds=1.2))
    service.tick(now=ORIGIN + timedelta(seconds=1.3))
    assert service.load(command.id).state == "EXECUTING"
    service.recover(ORIGIN + timedelta(seconds=1.4))
    assert service.load(command.id).state == "FAILED"
    assert service.adapter.reductions(ORIGIN + timedelta(seconds=2)) == {}
    assert (
        service.detail(command.id, principal, ORIGIN)
        .timeline[-1]
        .reason.startswith("RUNTIME_RECOVERY")
    )
    repo.close()


def test_permission_scope_expiry_and_decision_revision_fail_closed() -> None:
    repo, service, principal, approval = fixture()
    for bad in [
        Principal(
            "viewer",
            repo.org_id,
            repo.facility_id,
            frozenset({"dispatch.read"}),
            ORIGIN + timedelta(hours=1),
        ),
        Principal(
            "other", uuid4(), repo.facility_id, SIMULATION_PERMISSIONS, ORIGIN + timedelta(hours=1)
        ),
        Principal("expired", repo.org_id, repo.facility_id, SIMULATION_PERMISSIONS, ORIGIN),
    ]:
        with pytest.raises(PermissionDenied):
            service.request(approval, bad, now=ORIGIN)
    command = service.request(approval, principal, now=ORIGIN)
    with pytest.raises(Rejected, match="DISPATCH_REVISION_CONFLICT"):
        decide(service, principal, command.id, command.revision + 1, "approve", ORIGIN)
    threshold(repo, 449)
    rejected = decide(service, principal, command.id, command.revision, "approve", ORIGIN)
    assert rejected.state == "REJECTED" and rejected.reason == "DISPATCH_INPUT_NOT_READY"
    assert not repo.db.execute("SELECT 1 FROM simulator_commands").fetchone()
    repo.close()


def test_decision_idempotency_and_explicit_rejection() -> None:
    repo, service, principal, approval = fixture()
    command = service.request(approval, principal, now=ORIGIN)
    request_id = uuid4()
    first = decide(service, principal, command.id, command.revision, "reject", ORIGIN, request_id)
    assert first.state == "REJECTED"
    assert (
        decide(service, principal, command.id, command.revision, "reject", ORIGIN, request_id)
        == first
    )
    with pytest.raises(Rejected, match="IDEMPOTENCY_CONFLICT"):
        decide(service, principal, command.id, command.revision, "approve", ORIGIN, request_id)
    assert len(service.events()) == 2
    repo.close()


def test_api_rejects_role_spoofing_and_unknown_routes(tmp_path: Path) -> None:
    path = tmp_path / "edge.db"
    repo = Repository(path)
    org, facility = repo.org_id, repo.facility_id
    repo.close()
    viewer = Principal(
        "viewer", org, facility, frozenset({"dispatch.read"}), ORIGIN + timedelta(days=365)
    )
    with TestClient(
        create_app("a" * 64, uuid4(), path, simulate=False, principal=viewer)
    ) as client:
        headers = {"Authorization": "Bearer " + "a" * 64}
        assert client.get("/api/v1/dispatch").status_code == 401
        assert (
            client.get("/api/v1/dispatch", headers=headers | {"Origin": "http://evil"}).status_code
            == 401
        )
        assert client.get("/api/v1/dispatch", headers=headers).status_code == 200
        body = {"request_id": str(uuid4()), "run_id": str(uuid4())}
        assert (
            client.post(
                "/api/v1/dispatch/requests",
                headers=headers,
                json=body | {"role": "FACILITY_MANAGER"},
            ).status_code
            == 403
        )
        assert (
            client.post("/api/v1/dispatch/requests", headers=headers, json=body).status_code == 403
        )
        assert (
            client.post("/api/v1/dispatch/decisions", headers=headers, json={}).status_code == 422
        )
        assert client.post("/api/v1/dispatch", headers=headers, json={}).status_code == 405


def test_upgrade_from_phase5_preserves_history(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    repo = Repository(path)
    original = repo.registry.records()
    repo.db.executescript(
        "DROP TABLE incidents; DROP TABLE incident_requests; DROP TABLE incident_history; "
        "DROP TABLE incident_cursor; DROP TABLE production_reports; "
        "DROP TABLE sync_conflicts; DROP TABLE sync_streams; DROP TABLE edge_identity; "
        "DROP TABLE finance_outbox; DROP TABLE finance_ledger; "
        "DROP TABLE finance_verifications; DROP TABLE finance_tariffs; "
        "DROP TABLE simulator_commands; DROP TABLE dispatch_requests; "
        "DROP TABLE dispatch_outbox; DROP TABLE dispatch_commands; PRAGMA user_version=4;"
    )
    repo.close()
    repo = Repository(path)
    assert repo.db.execute("PRAGMA user_version").fetchone()[0] == 11
    assert repo.registry.records() == original
    repo.close()


def test_simulated_duration_completion_has_no_verified_savings() -> None:
    repo, service, principal, approval = fixture()
    command = service.request(approval, principal, now=ORIGIN)
    decide(service, principal, command.id, command.revision, "approve", ORIGIN)
    service.tick(now=ORIGIN + timedelta(seconds=0.1))
    service.tick(now=ORIGIN + timedelta(seconds=1.2))
    service.tick(now=ORIGIN + timedelta(seconds=1.3))
    adapter = SimulatorAdapter(repo.registry)
    for second in range(2, 304):
        at = ORIGIN + timedelta(seconds=second)
        batch = adapter.poll(2000 + second, at, "normal")
        assert batch
        repo.ingest(batch, at)
        service.tick(now=at + timedelta(seconds=0.1))
        if service.load(command.id).state == "COMPLETED":
            break
    final = service.load(command.id)
    assert final.state == "COMPLETED"
    assert final.reason.startswith("Simulator duration elapsed")
    assert service.adapter.reductions(ORIGIN + timedelta(seconds=63)) == {}
    assert (
        service.detail(command.id, principal, ORIGIN).timeline[-1].event_type == "DispatchCompleted"
    )
    assert not repo.db.execute("SELECT name FROM sqlite_master WHERE name='savings'").fetchone()
    repo.close()


def test_disconnection_and_monitor_gap_fail_active_command() -> None:
    repo, service, principal, approval = fixture()
    command = service.request(approval, principal, now=ORIGIN)
    decide(service, principal, command.id, command.revision, "approve", ORIGIN)
    service.tick(now=ORIGIN + timedelta(seconds=0.1))
    service.tick(now=ORIGIN + timedelta(seconds=1.2))
    service.tick(now=ORIGIN + timedelta(seconds=1.3))
    service.tick(unavailable=True, now=ORIGIN + timedelta(seconds=2))
    assert service.load(command.id).state == "FAILED"
    assert service.adapter.reductions(ORIGIN + timedelta(seconds=2)) == {}
    repo.close()

    repo, service, principal, approval = fixture()
    command = service.request(approval, principal, now=ORIGIN)
    decide(service, principal, command.id, command.revision, "approve", ORIGIN)
    service.tick(now=ORIGIN + timedelta(seconds=0.1))
    service.tick(now=ORIGIN + timedelta(seconds=1.2))
    service.tick(now=ORIGIN + timedelta(seconds=1.3))
    service.tick(now=ORIGIN + timedelta(seconds=7))
    assert service.load(command.id).state == "FAILED"
    assert service.load(command.id).reason == "EXECUTION_MONITORING_GAP"
    repo.close()


def test_worker_transaction_rollback_then_fails_uncertain_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, service, principal, approval = fixture()
    command = service.request(approval, principal, now=ORIGIN)
    decide(service, principal, command.id, command.revision, "approve", ORIGIN)
    original_event = service.event

    def fail(*args: object) -> None:
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr(service, "event", fail)
    service.tick(now=ORIGIN + timedelta(seconds=0.1))
    assert service.worker_error == "DISPATCH_WORKER_OR_STORAGE_FAILED"
    assert service.load(command.id).state == "QUEUED"
    assert not repo.db.execute("SELECT 1 FROM simulator_commands").fetchone()
    monkeypatch.setattr(service, "event", original_event)
    service.tick(now=ORIGIN + timedelta(seconds=0.2))
    assert service.worker_error is None
    assert service.load(command.id).state == "FAILED"
    assert service.load(command.id).reason.startswith("RUNTIME_RECOVERY")
    repo.close()
