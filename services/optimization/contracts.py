from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator, model_validator

from edge.runtime.contracts import Contract
from services.registry.contracts import Identifier, RegistryRecord
from services.telemetry.contracts import StoredPoint

Nonnegative = Annotated[float, Field(ge=0, le=100000000, allow_inf_nan=False)]


class PolicyInput(Contract):
    name: str = Field(min_length=1, max_length=100, pattern=r".*\S.*")
    effective_from: AwareDatetime
    effective_until: AwareDatetime
    max_duration_seconds: int = Field(ge=60, le=1800)
    max_total_reduction_kw: float = Field(gt=0, le=100000000, allow_inf_nan=False)
    # Relative production/wear/preference penalties; lower is preferred, never overrides a gate.
    asset_penalties: dict[Identifier, int] = Field(default={}, max_length=100)
    simulation_rate_per_kwh: Decimal | None = Field(
        default=None, ge=0, le=1000000, max_digits=14, decimal_places=6
    )
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")

    @field_validator("effective_from", "effective_until")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @field_validator("asset_penalties")
    @classmethod
    def penalties(cls, value: dict[str, int]) -> dict[str, int]:
        if any(not 0 <= n <= 10000 for n in value.values()):
            raise ValueError("Penalty must be between 0 and 10000")
        return value

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.effective_until <= self.effective_from:
            raise ValueError("Policy window must be ordered")
        return self


class PolicyWrite(Contract):
    request_id: UUID
    policy: PolicyInput


class OptimizationPolicy(PolicyInput):
    id: UUID
    version: Literal["1"] = "1"
    org_id: UUID
    facility_id: UUID
    created_at: datetime
    mode: Literal["SIMULATION"] = "SIMULATION"


class RunRequest(Contract):
    request_id: UUID
    policy_id: UUID
    duration_seconds: int = Field(ge=60, le=1800)


class ConstraintResult(Contract):
    code: str
    kind: Literal["HARD", "SOFT"]
    passed: bool
    detail: str


class CandidateEvaluation(Contract):
    asset_id: str
    name: str
    current_kw: float | None
    available_kw: Nonnegative
    selected_kw: Nonnegative = 0
    penalty: int
    eligible: bool
    constraints: list[ConstraintResult]


class EconomicEstimate(Contract):
    status: Literal["ESTIMATED", "INCOMPLETE"]
    amount: Decimal | None
    currency: str
    simulation_rate_per_kwh: Decimal | None
    energy_kwh: Decimal
    method: str = "simulation-gross-curtailment-v1: reduction_kW * seconds / 3600 * rate"
    assumptions: str = (
        "SIMULATED gross avoided energy only; constant reduction assumed. "
        "Excludes rebound, production costs, demand charges, settlement and verified savings."
    )


class Proposal(Contract):
    id: UUID
    state: Literal["PROPOSED"] = "PROPOSED"
    expected_reduction_kw: float
    expires_at: datetime
    economic_estimate: EconomicEstimate
    explanation: str
    authorization: Literal["NOT_AUTHORIZED"] = "NOT_AUTHORIZED"


class OptimizationRun(Contract):
    sequence: int = 0
    id: UUID
    org_id: UUID
    facility_id: UUID
    mode: Literal["SIMULATION"] = "SIMULATION"
    algorithm_version: Literal["bounded-curtailment-v1"] = "bounded-curtailment-v1"
    created_at: datetime
    ends_at: datetime
    status: Literal["PROPOSED", "INFEASIBLE", "NO_ACTION"]
    request: RunRequest
    policy: OptimizationPolicy
    prediction_id: UUID | None
    risk_ids: list[UUID]
    registry_digest: str
    registry: list[RegistryRecord]
    telemetry: list[StoredPoint]
    forecast_peak_kw: float | None
    threshold_kw: float | None
    required_reduction_kw: float | None
    constraints: list[ConstraintResult]
    candidates: list[CandidateEvaluation]
    proposal: Proposal | None
    explanation: str


class OptimizationEvent(Contract):
    sequence: int
    event_id: UUID
    event_type: Literal[
        "OptimizationPolicyCreated",
        "OptimizationStarted",
        "ProposalCreated",
        "OptimizationInfeasible",
        "OptimizationNoAction",
    ]
    schema_version: Literal["1"] = "1"
    occurred_at: datetime
    producer: Literal["edge.optimization"] = "edge.optimization"
    org_id: UUID
    facility_id: UUID
    actor: Literal["local-simulation-session"] = "local-simulation-session"
    correlation_id: UUID
    causation_id: UUID
    idempotency_key: UUID
    resource_id: UUID


class OptimizationSnapshot(Contract):
    mode: Literal["SIMULATION"] = "SIMULATION"
    observed_at: datetime
    timezone: str
    policies: list[OptimizationPolicy]
    latest: OptimizationRun | None
    latest_is_current: bool
    pending_events: int
    run_count: int
    capacity: int
