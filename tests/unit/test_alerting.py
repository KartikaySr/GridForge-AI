import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from edge.runtime.app import create_app
from edge.storage.repository import Rejected, Repository
from services.alerting.contracts import IncidentAction
from services.alerting.service import IncidentService
from services.dispatch.permissions import PermissionDenied, Principal
from services.forecasting.contracts import RiskRecord
from services.forecasting.service import ForecastService
from services.security.policy import ALL, ROLES


def actor(repo: Repository) -> Principal:
    return Principal(
        "investigator", repo.org_id, repo.facility_id, ALL, datetime.now(UTC) + timedelta(hours=1)
    )


def risk(repo: Repository) -> RiskRecord:
    now = datetime.now(UTC)
    return RiskRecord(
        id=uuid4(),
        org_id=repo.org_id,
        facility_id=repo.facility_id,
        state="OPEN",
        opened_at=now,
        updated_at=now,
        first_prediction_id=uuid4(),
        latest_prediction_id=uuid4(),
        threshold_kw=100,
        threshold_revision=1,
        predicted_peak_kw=120,
        window_start=now,
        window_end=now + timedelta(minutes=30),
        reason="fixture",
    )


def emit(repo: Repository, item: RiskRecord, event_type: str = "RiskDetected") -> None:
    service = ForecastService(repo)
    with repo.lock, repo.db:
        repo.db.execute(
            "INSERT OR REPLACE INTO risks VALUES (?,?,?,?,?)",
            (
                str(item.id),
                str(item.org_id),
                str(item.facility_id),
                item.state,
                item.model_dump_json(),
            ),
        )
        service.emit(item, event_type, uuid4(), datetime.now(UTC))


def action(item: object, **changes: object) -> IncidentAction:
    from services.alerting.contracts import Incident

    assert isinstance(item, Incident)
    return IncidentAction.model_validate(
        dict(
            request_id=uuid4(),
            incident_id=item.id,
            expected_revision=item.revision,
            action="acknowledge",
            note="Reviewed",
        )
        | changes
    )


def test_replay_restart_and_source_gated_closure(tmp_path: Path) -> None:
    path = tmp_path / "incidents.db"
    repo = Repository(path)
    service = IncidentService(repo)
    user = actor(repo)
    source = risk(repo)
    emit(repo, source)
    service.tick()
    incident = service.snapshot(user).incidents[0]
    service.tick()
    assert service.snapshot(user).incidents == [incident]
    write = action(incident)
    acknowledged = service.act(write, user)
    assert acknowledged.status == "ACKNOWLEDGED"
    assert service.act(write, user) == acknowledged
    with pytest.raises(Rejected, match="CONFLICT"):
        service.act(write.model_copy(update={"note": "Changed"}), user)
    with pytest.raises(Rejected, match="STILL_ACTIVE"):
        service.act(action(acknowledged, action="resolve"), user)
    source.state = "RESOLVED"
    emit(repo, source, "RiskResolved")
    service.tick()
    current = service.snapshot(user).incidents[0]
    with pytest.raises(Rejected, match="REVISION"):
        service.act(action(acknowledged, action="resolve"), user)
    closed = service.act(action(current, action="resolve"), user)
    assert closed.status == "CLOSED" and closed.source_state == "RESOLVED"
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE"):
        repo.db.execute("DELETE FROM incident_history")
    repo.close()
    repo = Repository(path)
    service = IncidentService(repo)
    assert service.snapshot(user).incidents == [closed]
    assert service.snapshot(user).pending_events == 0
    assert repo.db.execute("SELECT COUNT(*) FROM dispatch_commands").fetchone()[0] == 0
    repo.close()


def test_scope_permissions_source_replay_and_superseded() -> None:
    repo = Repository(None)
    service = IncidentService(repo)
    user = actor(repo)
    source = risk(repo)
    emit(repo, source)
    service.tick()
    incident = service.snapshot(user).incidents[0]
    for denied in [
        replace(user, permissions=ROLES["VIEWER"]),
        replace(user, facility_id=uuid4()),
        replace(user, expires_at=datetime.now(UTC) - timedelta(seconds=1)),
    ]:
        with pytest.raises(PermissionDenied):
            service.act(action(incident), denied)
    service.act(action(incident), user)
    source.state = "SUPERSEDED"
    emit(repo, source, "RiskSuperseded")
    service.tick()
    current = service.snapshot(user).incidents[0]
    closed = service.act(action(current, action="resolve"), user)
    assert closed.source_state == "SUPERSEDED" and closed.status == "CLOSED"
    repo.close()


def test_worker_transaction_rollback_does_not_skip_events() -> None:
    repo = Repository(None)
    service = IncidentService(repo)
    source = risk(repo)
    emit(repo, source)
    repo.db.execute(
        "CREATE TRIGGER reject_incident BEFORE INSERT ON incidents "
        "BEGIN SELECT RAISE(ABORT,'test'); END;"
    )
    with pytest.raises(sqlite3.IntegrityError):
        service.tick()
    assert service.snapshot(actor(repo)).processed_sequence == 0
    repo.db.execute("DROP TRIGGER reject_incident")
    service.tick()
    assert service.snapshot(actor(repo)).total == 1
    repo.close()


def test_secure_api_and_cursor_validation() -> None:
    app = create_app("a" * 64, uuid4(), simulate=False)
    headers = {"Authorization": "Bearer " + "a" * 64}
    with TestClient(app) as client:
        assert client.get("/api/v1/incidents", headers=headers).status_code == 403
        assert (
            client.post(
                "/api/v1/identity/bootstrap",
                headers=headers,
                json={"username": "admin", "password": "incident-test-password"},
            ).status_code
            == 200
        )
        assert client.get("/api/v1/incidents", headers=headers).json()["total"] == 0
        assert (
            client.post(
                "/api/v1/incidents/history", headers=headers, json={"before": -1}
            ).status_code
            == 422
        )
        assert client.post("/api/v1/incidents/actions", headers=headers, json={}).status_code == 422
