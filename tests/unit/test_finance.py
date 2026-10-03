from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from edge.connectors.simulator import SimulatorAdapter
from edge.storage.repository import Rejected, Repository
from services.dispatch.contracts import DispatchCommand
from services.dispatch.permissions import Principal
from services.dispatch.service import DispatchService
from services.finance.contracts import EnergyBand, TariffInput, TariffWrite, VerificationRequest
from services.finance.service import FinanceService
from tests.support import create_app
from tests.unit.test_dispatch import decide, fixture
from tests.unit.test_forecasting import ORIGIN, seed


def completed_command() -> tuple[Repository, DispatchService, Principal, DispatchCommand]:
    repo, dispatch, principal, approval = fixture()
    command = dispatch.request(approval, principal, now=ORIGIN)
    decide(dispatch, principal, command.id, command.revision, "approve", ORIGIN)
    for second in (0.1, 1.2, 1.3):
        dispatch.tick(now=ORIGIN + timedelta(seconds=second))
    adapter = SimulatorAdapter(repo.registry)
    for second in range(2, 304):
        at = ORIGIN + timedelta(seconds=second)
        batch = adapter.poll(2000 + second, at, "normal")
        assert batch
        repo.ingest(batch, at)
        dispatch.tick(now=at + timedelta(seconds=0.1))
        if dispatch.load(command.id).state == "COMPLETED":
            break
    assert dispatch.load(command.id).state == "COMPLETED"
    return repo, dispatch, principal, command


def tariff_write(rate: str = "0.15") -> TariffWrite:
    return TariffWrite(
        request_id=uuid4(),
        tariff=TariffInput(
            name="Declared synthetic flat rate",
            currency="USD",
            effective_from=ORIGIN - timedelta(days=1),
            effective_until=ORIGIN + timedelta(days=1),
            billing_period_start=ORIGIN - timedelta(days=1),
            billing_period_end=ORIGIN + timedelta(days=1),
            demand_charge_rate_per_kw=Decimal("10.00"),
            energy_bands=[
                EnergyBand(
                    starts_at=ORIGIN - timedelta(days=1),
                    ends_at=ORIGIN + timedelta(days=1),
                    rate_per_kwh=Decimal(rate),
                )
            ],
        ),
    )


def replace_measurements(repo: Repository, execution_kw: float, rebound_kw: float) -> None:
    """Reset post-command fixture points while retaining dispatch/forecast audit records."""
    since = ((ORIGIN + timedelta(seconds=2)).isoformat(),)
    with repo.lock, repo.db:
        repo.db.execute(
            "DELETE FROM latest WHERE telemetry_id IN "
            "(SELECT id FROM telemetry WHERE event_time>=?)",
            since,
        )
        repo.db.execute(
            "DELETE FROM outbox WHERE id IN (SELECT id FROM telemetry WHERE event_time>=?)",
            since,
        )
        repo.db.execute("DELETE FROM telemetry WHERE event_time>=?", since)
    seed(repo, ORIGIN + timedelta(seconds=2), 5, kw=execution_kw)
    seed(repo, ORIGIN + timedelta(seconds=302), 5, kw=rebound_kw)


def test_finance_rebound_ledger_and_idempotency() -> None:
    repo, _, principal, command = completed_command()
    service = FinanceService(repo)
    write = tariff_write()
    tariff = service.tariff(write, principal, ORIGIN)
    assert service.tariff(write, principal, ORIGIN) == tariff
    with pytest.raises(Rejected, match="IDEMPOTENCY_CONFLICT"):
        service.tariff(
            write.model_copy(update={"tariff": tariff_write("0.2").tariff}), principal, ORIGIN
        )
    # Replace simulator's noisy execution observations with declared, complete synthetic
    # measurements so the finance test isolates baseline and rebound math.
    replace_measurements(repo, 90, 102)
    request = VerificationRequest(request_id=uuid4(), command_id=command.id, tariff_id=tariff.id)
    case = service.start(request, principal, ORIGIN + timedelta(seconds=304))
    assert case.status == "PENDING"
    assert service.start(request, principal, ORIGIN + timedelta(seconds=304)).id == case.id
    assert [e.status for e in service.snapshot(principal, ORIGIN).ledger] == ["ESTIMATED"]
    service.tick(ORIGIN + timedelta(seconds=607))
    resolved = service.snapshot(principal, ORIGIN + timedelta(seconds=607))
    result = resolved.verifications[0]
    assert result.status == "VERIFIED"
    assert result.execution and result.execution.valid_slots == 300
    assert result.rebound and result.rebound.valid_slots == 300
    assert result.net_energy_value == Decimal("0.50")
    assert result.rebound_kwh == Decimal("0.8333333333333333333333333333")
    assert result.demand_charge.status == "INCOMPLETE"
    assert result.demand_charge.amount is None
    assert [entry.status for entry in reversed(resolved.ledger)] == ["ESTIMATED", "VERIFIED"]
    assert resolved.ledger[0].amount == Decimal("0.50")
    service.tick(ORIGIN + timedelta(seconds=608))
    assert len(service.snapshot(principal, ORIGIN).ledger) == 2
    assert [event.event_type for event in service.events()] == [
        "TariffVersionCreated",
        "VerificationStarted",
        "SavingsEstimated",
        "SavingsVerified",
        "VerificationCompleted",
    ]
    repo.close()


def test_time_band_rebound_can_create_a_verified_loss() -> None:
    repo, _, principal, command = completed_command()
    service = FinanceService(repo)
    base = tariff_write("0.10")
    switch = ORIGIN + timedelta(seconds=302)
    inputs = base.tariff.model_copy(
        update={
            "energy_bands": [
                EnergyBand(
                    starts_at=ORIGIN - timedelta(days=1),
                    ends_at=switch,
                    rate_per_kwh=Decimal("0.10"),
                ),
                EnergyBand(
                    starts_at=switch,
                    ends_at=ORIGIN + timedelta(days=1),
                    rate_per_kwh=Decimal("0.30"),
                ),
            ]
        }
    )
    tariff = service.tariff(base.model_copy(update={"tariff": inputs}), principal, ORIGIN)
    replace_measurements(repo, 90, 112)
    case = service.start(
        VerificationRequest(request_id=uuid4(), command_id=command.id, tariff_id=tariff.id),
        principal,
        ORIGIN + timedelta(seconds=304),
    )
    assert case.status == "PENDING"
    service.tick(ORIGIN + timedelta(seconds=607))
    result = service.snapshot(principal, ORIGIN + timedelta(seconds=607)).verifications[0]
    assert result.status == "VERIFIED"
    assert result.gross_avoided_cost == Decimal("0.42")
    assert result.rebound_cost == Decimal("1.50")
    assert result.net_energy_value == Decimal("-1.08")
    assert service.snapshot(principal, ORIGIN).ledger[0].amount == Decimal("-1.08")
    repo.close()


def test_incomplete_data_never_creates_verified_ledger() -> None:
    repo, _, principal, command = completed_command()
    service = FinanceService(repo)
    tariff = service.tariff(tariff_write(), principal, ORIGIN)
    request = VerificationRequest(request_id=uuid4(), command_id=command.id, tariff_id=tariff.id)
    service.start(request, principal, ORIGIN + timedelta(seconds=304))
    service.tick(ORIGIN + timedelta(seconds=607))
    snapshot = service.snapshot(principal, ORIGIN + timedelta(seconds=607))
    assert snapshot.verifications[0].status == "INCOMPLETE"
    assert snapshot.verifications[0].net_energy_value is None
    assert all(entry.status != "VERIFIED" for entry in snapshot.ledger)
    repo.close()


def test_tariff_rejects_overlapping_bands() -> None:
    write = tariff_write()
    band = write.tariff.energy_bands[0]
    with pytest.raises(ValidationError):
        TariffInput.model_validate(write.tariff.model_dump() | {"energy_bands": [band, band]})


def test_finance_http_auth_scope_and_schema(tmp_path: Path) -> None:
    path = tmp_path / "finance.db"
    repo = Repository(path)
    org, facility = repo.org_id, repo.facility_id
    repo.close()
    viewer = Principal(
        "viewer", org, facility, frozenset({"finance.read"}), ORIGIN + timedelta(days=365)
    )
    headers = {"Authorization": "Bearer " + "a" * 64}
    with TestClient(
        create_app("a" * 64, uuid4(), path, simulate=False, principal=viewer)
    ) as client:
        assert client.get("/api/v1/finance").status_code == 401
        assert client.get("/api/v1/finance", headers=headers).status_code == 200
        assert (
            client.get("/api/v1/finance", headers=headers | {"Origin": "https://evil"}).status_code
            == 401
        )
        write = tariff_write().model_dump(mode="json")
        assert (
            client.post(
                "/api/v1/finance/tariffs", headers=headers, json=write | {"role": "admin"}
            ).status_code
            == 403
        )
        assert (
            client.post("/api/v1/finance/tariffs", headers=headers, json=write).status_code == 403
        )
        assert (
            client.post("/api/v1/finance/verifications", headers=headers, json={}).status_code
            == 403
        )
