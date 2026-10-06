from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from edge.runtime.contracts import Contract


class Incident(Contract):
    schema_version: Literal["1"] = "1"
    org_id: UUID
    facility_id: UUID
    id: UUID
    mode: Literal["SIMULATION"] = "SIMULATION"
    sync_state: Literal["LOCAL_ONLY"] = "LOCAL_ONLY"
    risk_id: UUID
    revision: int
    source_state: Literal["OPEN", "RESOLVED", "SUPERSEDED"]
    status: Literal["OPEN", "ACKNOWLEDGED", "CLOSED"]
    opened_at: datetime
    updated_at: datetime
    prediction_id: UUID
    threshold_kw: float
    predicted_peak_kw: float
    actor: str | None = None
    note: str | None = None


class IncidentAction(Contract):
    request_id: UUID
    incident_id: UUID
    expected_revision: int = Field(ge=1)
    action: Literal["acknowledge", "resolve"]
    note: str = Field(min_length=1, max_length=500)

    @field_validator("note")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A nonblank investigation note is required")
        return value.strip()


class IncidentSnapshot(Contract):
    mode: Literal["SIMULATION"] = "SIMULATION"
    observed_at: datetime
    incidents: list[Incident]
    worker_error: str | None
    processed_sequence: int
    pending_events: int
    total: int
    next_before: int | None


class IncidentQuery(Contract):
    before: int | None = Field(default=None, ge=1, le=9223372036854775807)
