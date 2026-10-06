import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from edge.runtime.app import create_app
from edge.storage.repository import Rejected, Repository
from services.dispatch.permissions import PermissionDenied, Principal
from services.reporting.contracts import ProductionWrite, ReportComparisonRequest
from services.reporting.service import ReportingService
from services.security.policy import ALL, ROLES
from simulator.factory import factory_batch

ORIGIN = datetime(2026, 9, 20, 10, tzinfo=UTC)


def actor(repo: Repository) -> Principal:
    return Principal(
        "reporter", repo.org_id, repo.facility_id, ALL, datetime.now(UTC) + timedelta(hours=1)
    )


def declaration(start: datetime = ORIGIN, good: str = "1", reject: str = "0") -> ProductionWrite:
    return ProductionWrite(
        request_id=uuid4(),
        product="casting-A",
        starts_at=start,
        ends_at=start + timedelta(seconds=60),
        asset_ids=["SIM-1"],
        good_tonnes=Decimal(good),
        rejected_tonnes=Decimal(reject),
        note="Synthetic matched fixture",
    )


def ingest(
    repo: Repository,
    start: datetime,
    watts: float = 60000,
    missing: bool = False,
    bad: bool = False,
) -> None:
    for second in range(60):
        if missing and second == 10:
            continue
        at = start + timedelta(seconds=second)
        batch = factory_batch(repo.org_id, repo.facility_id, 57, int(at.timestamp()), at, "normal")
        batch.points = [
            batch.points[0].model_copy(
                update={"value": watts, "quality": "BAD" if bad and second == 10 else "GOOD"}
            )
        ]
        repo.ingest(batch, at)


def test_measured_sec_comparison_replay_restart_and_immutability(tmp_path: Path) -> None:
    path = tmp_path / "report.db"
    repo = Repository(path)
    user = actor(repo)
    service = ReportingService(repo)
    ingest(repo, ORIGIN)
    ingest(repo, ORIGIN + timedelta(seconds=60), 54000)
    write = declaration()
    a = service.create(write, user, datetime.now(UTC))
    assert a.energy_kwh == 1 and a.sec_kwh_per_good_tonne == 1
    assert a.valid_seconds == 60 and a.status == "COMPLETE"
    assert service.create(write, user, datetime.now(UTC)) == a
    with pytest.raises(Rejected, match="CONFLICT"):
        service.create(write.model_copy(update={"note": "different"}), user, datetime.now(UTC))
    b = service.create(declaration(ORIGIN + timedelta(seconds=60)), user, datetime.now(UTC))
    result = service.compare(ReportComparisonRequest(baseline_id=a.id, comparison_id=b.id), user)
    assert result.status == "COMPARABLE" and result.sec_change_percent == -10
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE"):
        repo.db.execute("DELETE FROM production_reports")
    repo.close()
    repo = Repository(path)
    assert ReportingService(repo).snapshot(user).reports[0] == b
    assert repo.db.execute("PRAGMA user_version").fetchone()[0] == 10
    repo.close()


@pytest.mark.parametrize("missing,bad", [(True, False), (False, True)])
def test_incomplete_data_never_produces_sec(missing: bool, bad: bool) -> None:
    repo = Repository(None)
    ingest(repo, ORIGIN, missing=missing, bad=bad)
    report = ReportingService(repo).create(declaration(), actor(repo), datetime.now(UTC))
    assert report.status == "INCOMPLETE" and report.valid_seconds == 59
    assert report.energy_kwh is None and report.sec_kwh_per_good_tonne is None
    repo.close()


@pytest.mark.parametrize("good,reject", [("0.9", "0"), ("1", "0.1")])
def test_production_regression_blocks_improvement(good: str, reject: str) -> None:
    repo = Repository(None)
    service, user = ReportingService(repo), actor(repo)
    ingest(repo, ORIGIN)
    ingest(repo, ORIGIN + timedelta(seconds=60), 30000)
    a = service.create(declaration(), user, datetime.now(UTC))
    b = service.create(
        declaration(ORIGIN + timedelta(seconds=60), good, reject), user, datetime.now(UTC)
    )
    result = service.compare(ReportComparisonRequest(baseline_id=a.id, comparison_id=b.id), user)
    assert result.status == "PRODUCTION_REGRESSION" and result.sec_change_percent is None
    repo.close()


def test_scope_permission_window_and_boundaries() -> None:
    repo = Repository(None)
    user, service = actor(repo), ReportingService(repo)
    for denied in [
        replace(user, facility_id=uuid4()),
        replace(user, permissions=ROLES["VIEWER"]),
        replace(user, expires_at=ORIGIN),
    ]:
        with pytest.raises(PermissionDenied):
            service.create(declaration(), denied, datetime.now(UTC))
    with pytest.raises(Rejected, match="NOT_CLOSED"):
        service.create(declaration(), user, ORIGIN)
    with pytest.raises(Rejected, match="MAPPING"):
        service.create(
            declaration().model_copy(update={"asset_ids": ["unknown"]}), user, datetime.now(UTC)
        )
    ingest(repo, ORIGIN)
    a = service.create(declaration(), user, datetime.now(UTC))
    result = service.compare(ReportComparisonRequest(baseline_id=a.id, comparison_id=a.id), user)
    assert result.status == "NOT_COMPARABLE" and result.sec_change_percent is None
    repo.close()


def test_api_requires_identity_and_supports_report_history() -> None:
    app = create_app("a" * 64, uuid4(), simulate=False)
    headers = {"Authorization": "Bearer " + "a" * 64}
    with TestClient(app) as client:
        assert client.get("/api/v1/reports", headers=headers).status_code == 403
        assert (
            client.post(
                "/api/v1/identity/bootstrap",
                headers=headers,
                json={"username": "admin", "password": "test-report-password"},
            ).status_code
            == 200
        )
        ingest(app.state.telemetry.repo, ORIGIN)
        response = client.post(
            "/api/v1/reports/production",
            headers=headers,
            json=declaration().model_dump(mode="json"),
        )
        assert response.status_code == 200, response.text
        assert response.json()["energy_kwh"] == "1.0" or Decimal(response.json()["energy_kwh"]) == 1
        history = client.post("/api/v1/reports/history", headers=headers, json={"before": 1})
        assert history.status_code == 200 and not history.json()["reports"]
        assert (
            client.post("/api/v1/reports/history", headers=headers, json={"before": -1}).status_code
            == 422
        )


def test_pagination_and_incomparable_product() -> None:
    repo = Repository(None)
    service, user = ReportingService(repo), actor(repo)
    ingest(repo, ORIGIN)
    ingest(repo, ORIGIN + timedelta(seconds=60))
    a = service.create(declaration(), user, datetime.now(UTC))
    b = service.create(
        declaration(ORIGIN + timedelta(seconds=60)).model_copy(update={"product": "casting-B"}),
        user,
        datetime.now(UTC),
    )
    comparison = service.compare(
        ReportComparisonRequest(baseline_id=a.id, comparison_id=b.id), user
    )
    assert comparison.status == "NOT_COMPARABLE"
    assert "PRODUCT_MISMATCH" in comparison.reasons
    assert comparison.sec_change_percent is None
    for _ in range(19):
        service.create(declaration(), user, datetime.now(UTC))
    first = service.snapshot(user)
    assert len(first.reports) == 20 and first.next_before is not None
    second = service.snapshot(user, first.next_before)
    assert [r.id for r in second.reports] == [a.id]
    assert second.next_before is None
    with pytest.raises(Rejected, match="NOT_FOUND"):
        service.compare(ReportComparisonRequest(baseline_id=a.id, comparison_id=uuid4()), user)
    repo.close()
