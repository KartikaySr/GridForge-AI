from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator, model_validator

from edge.runtime.contracts import Contract

MoneyRate = Decimal


class EnergyBand(Contract):
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    rate_per_kwh: MoneyRate = Field(ge=0, le=1000000, max_digits=14, decimal_places=6)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("Energy band must have positive duration")
        return self


class TariffInput(Contract):
    name: str = Field(min_length=1, max_length=100, pattern=r".*\S.*")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    effective_from: AwareDatetime
    effective_until: AwareDatetime
    energy_bands: list[EnergyBand] = Field(min_length=1, max_length=100)
    billing_period_start: AwareDatetime
    billing_period_end: AwareDatetime
    demand_charge_rate_per_kw: MoneyRate | None = Field(
        default=None, ge=0, le=1000000, max_digits=14, decimal_places=6
    )

    @field_validator(
        "effective_from", "effective_until", "billing_period_start", "billing_period_end"
    )
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if (
            self.effective_until <= self.effective_from
            or self.billing_period_end <= self.billing_period_start
        ):
            raise ValueError("Tariff and billing period windows must be ordered")
        bands = sorted(self.energy_bands, key=lambda b: b.starts_at)
        if any(
            b.starts_at < self.effective_from or b.ends_at > self.effective_until for b in bands
        ):
            raise ValueError("Bands must fit tariff effective window")
        if any(
            left.ends_at > right.starts_at for left, right in zip(bands, bands[1:], strict=False)
        ):
            raise ValueError("Energy bands must not overlap")
        return self


class TariffWrite(Contract):
    request_id: UUID
    tariff: TariffInput


class TariffVersion(TariffInput):
    id: UUID
    version: Literal["1"] = "1"
    org_id: UUID
    facility_id: UUID
    created_at: datetime
    mode: Literal["SIMULATION"] = "SIMULATION"
    source: Literal["USER_ENTERED_SIMULATION"] = "USER_ENTERED_SIMULATION"


class VerificationRequest(Contract):
    request_id: UUID
    command_id: UUID
    tariff_id: UUID


class WindowEvidence(Contract):
    starts_at: datetime
    ends_at: datetime
    expected_slots: int
    valid_slots: int
    first_row: int | None
    last_row: int | None
    source_digest: str
    baseline_energy_kwh: Decimal | None
    actual_energy_kwh: Decimal | None
    quality: Literal["COMPLETE", "INCOMPLETE"]
    reason: str | None


class DemandChargeAssessment(Contract):
    status: Literal["INCOMPLETE"] = "INCOMPLETE"
    billing_period_start: datetime
    billing_period_end: datetime
    rate_per_kw: Decimal | None
    billing_baseline_peak_kw: None = None
    billing_actual_peak_kw: None = None
    amount: None = None
    reason: str = (
        "Full billing-period interval demand, ratchets and utility rules are unavailable; "
        "no demand-charge savings claimed"
    )


class Verification(Contract):
    id: UUID
    request: VerificationRequest
    org_id: UUID
    facility_id: UUID
    mode: Literal["SIMULATION"] = "SIMULATION"
    status: Literal["PENDING", "VERIFIED", "INCOMPLETE"]
    created_at: datetime
    evaluated_at: datetime | None
    command_id: UUID
    run_id: UUID
    proposal_id: UUID
    prediction_id: UUID
    baseline_method: Literal["pre-dispatch-rolling-mean-flat-v1"] = (
        "pre-dispatch-rolling-mean-flat-v1"
    )
    baseline_kw: Decimal
    tariff: TariffVersion
    execution: WindowEvidence | None
    rebound: WindowEvidence | None
    expected_reduction_kw: Decimal
    measured_reduction_kw: Decimal | None
    rebound_kwh: Decimal | None
    net_energy_kwh: Decimal | None
    gross_avoided_cost: Decimal | None
    rebound_cost: Decimal | None
    net_energy_value: Decimal | None
    demand_charge: DemandChargeAssessment
    reason: str


class LedgerEntry(Contract):
    sequence: int
    id: UUID
    status: Literal["ESTIMATED", "VERIFIED"]
    occurred_at: datetime
    org_id: UUID
    facility_id: UUID
    verification_id: UUID
    command_id: UUID
    tariff_id: UUID
    currency: str
    amount: Decimal
    method: str
    input_digest: str
    note: str


class FinanceEvent(Contract):
    sequence: int
    event_id: UUID
    event_type: Literal[
        "TariffVersionCreated",
        "VerificationStarted",
        "VerificationCompleted",
        "VerificationIncomplete",
        "SavingsEstimated",
        "SavingsVerified",
    ]
    schema_version: Literal["1"] = "1"
    occurred_at: datetime
    producer: Literal["edge.finance"] = "edge.finance"
    org_id: UUID
    facility_id: UUID
    actor: str
    correlation_id: UUID
    causation_id: UUID
    idempotency_key: UUID
    resource_id: UUID


class FinanceSnapshot(Contract):
    mode: Literal["SIMULATION"] = "SIMULATION"
    observed_at: datetime
    timezone: str
    tariffs: list[TariffVersion]
    verifications: list[Verification]
    ledger: list[LedgerEntry]
    pending_events: int
    tariff_count: int
    verification_count: int
    worker_error: str | None
