from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator

from edge.runtime.contracts import Contract


class TelemetryPoint(Contract):
    schema_version: Literal["1"] = "1"
    org_id: UUID
    facility_id: UUID
    asset_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
    device_id: str = "factory-simulator-v1"
    line_id: str = "simulation-line"
    signal_id: str = "active-power"
    metric: Literal["active_power"] = "active_power"
    value: float = Field(allow_inf_nan=False, ge=0, le=100000000)
    unit: Literal["W", "kW"]
    quality: Literal["GOOD", "BAD"] = "GOOD"
    source: Literal["SIMULATOR"] = "SIMULATOR"
    event_time: AwareDatetime
    sequence: int = Field(ge=0)
    idempotency_key: UUID

    @field_validator("event_time")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class TelemetryBatch(Contract):
    points: list[TelemetryPoint] = Field(min_length=1, max_length=100)


class StoredPoint(TelemetryPoint):
    unit: Literal["kW"] = "kW"
    received_time: AwareDatetime
    flags: list[str]
    row_id: int
    mapping_id: str | None = None
    mapping_revision: int | None = None


class IngestResult(Contract):
    accepted: int
    duplicates: int


class TelemetryEvent(Contract):
    event_id: UUID
    event_type: Literal["TelemetryReceived"] = "TelemetryReceived"
    schema_version: Literal["1"] = "1"
    occurred_at: AwareDatetime
    producer: Literal["edge.telemetry"] = "edge.telemetry"
    org_id: UUID
    facility_id: UUID
    correlation_id: UUID
    causation_id: UUID
    actor: Literal["simulator"] = "simulator"
    idempotency_key: UUID
    payload: StoredPoint


class AssetState(Contract):
    asset_id: str
    label: str
    point: StoredPoint | None
    status: Literal["LIVE", "BAD", "STALE", "DISCONNECTED", "EMPTY"]


class TelemetrySnapshot(Contract):
    schema_version: Literal["1"] = "1"
    mode: Literal["SIMULATION"] = "SIMULATION"
    observed_at: AwareDatetime
    org_id: UUID
    facility_id: UUID
    facility_name: str = "Synthetic factory"
    timezone: str = "UTC"
    seed: int
    tick: int
    scenario: str
    worker_state: Literal["RUNNING", "FAILED"]
    cursor: int
    assets: list[AssetState]
    recent: list[StoredPoint]
    accepted: int
    duplicates: int
    rejected: int
    backpressure: int
    queue_depth: int
    queue_capacity: int
    pending_outbox: int
    storage_capacity: int
    storage_full: bool


class HistoryPage(Contract):
    points: list[StoredPoint]
    next_cursor: int | None


class ScenarioRequest(Contract):
    scenario: Literal["normal", "spike", "bad", "stale", "disconnected"]
