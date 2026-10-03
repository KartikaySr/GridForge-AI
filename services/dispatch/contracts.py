from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from edge.runtime.contracts import Contract

DispatchState = Literal[
    "PENDING_APPROVAL",
    "APPROVED",
    "QUEUED",
    "SENT",
    "ACKNOWLEDGED",
    "EXECUTING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "REJECTED",
]
Behavior = Literal["normal", "delayed_ack", "missing_ack", "failed_command"]


class ApprovalRequest(Contract):
    request_id: UUID
    run_id: UUID
    behavior: Behavior = "normal"


class DecisionRequest(Contract):
    request_id: UUID
    command_id: UUID
    expected_revision: int = Field(ge=1)
    action: Literal["approve", "reject", "cancel"]
    reason: str = Field(min_length=1, max_length=300, pattern=r".*\S.*")


class DispatchAction(Contract):
    asset_id: str
    reduction_kw: float


class ValidationEvidence(Contract):
    at: datetime
    prediction_id: UUID
    registry_digest: str
    telemetry_rows: list[int]


class DispatchCommand(Contract):
    id: UUID
    run_id: UUID
    proposal_id: UUID
    org_id: UUID
    facility_id: UUID
    mode: Literal["SIMULATION"] = "SIMULATION"
    adapter: Literal["durable-simulator-v1"] = "durable-simulator-v1"
    revision: int
    state: DispatchState
    created_at: datetime
    updated_at: datetime
    approval_deadline: datetime
    approved_by: str | None = None
    approved_until: datetime | None = None
    behavior: Behavior
    actions: list[DispatchAction]
    duration_seconds: int
    attempts: int = 0
    max_attempts: Literal[2] = 2
    ack_timeout_seconds: Literal[5] = 5
    sent_at: datetime | None = None
    acknowledged_at: datetime | None = None
    last_guard_at: datetime | None = None
    execution_started_at: datetime | None = None
    execution_ends_at: datetime | None = None
    reason: str
    validations: list[ValidationEvidence]


class DispatchEvent(Contract):
    sequence: int
    event_id: UUID
    schema_version: Literal["1"] = "1"
    event_type: str
    occurred_at: datetime
    producer: Literal["edge.dispatch"] = "edge.dispatch"
    org_id: UUID
    facility_id: UUID
    correlation_id: UUID
    causation_id: UUID
    idempotency_key: UUID
    actor: str
    command_id: UUID
    revision: int
    from_state: DispatchState | None
    to_state: DispatchState
    reason: str


class DispatchSnapshot(Contract):
    mode: Literal["SIMULATION"] = "SIMULATION"
    observed_at: datetime
    timezone: str
    actor: str
    identity_notice: str = (
        "Local simulation session; not a verified human identity or production role"
    )
    permissions: list[str]
    session_expires_at: datetime
    commands: list[DispatchCommand]
    pending_events: int
    command_count: int
    capacity: int
    worker_error: str | None


class DispatchDetail(Contract):
    command: DispatchCommand
    timeline: list[DispatchEvent]
