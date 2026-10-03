"""Phase 1 transport contracts; generate TypeScript from the runtime OpenAPI."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ComponentHealth(Contract):
    name: str
    state: Literal["READY", "FAILED", "NOT_CONFIGURED", "NOT_IMPLEMENTED"]
    detail: str


class RuntimeHealth(Contract):
    schema_version: Literal["1"] = "1"
    mode: Literal["SIMULATION"] = "SIMULATION"
    service: Literal["gridforge-edge"] = "gridforge-edge"
    status: Literal["READY"] = "READY"
    readiness_scope: Literal["shell-only", "telemetry"] = "shell-only"
    operational_ready: Literal[False] = False
    instance_id: UUID
    started_at: datetime
    observed_at: datetime
    uptime_seconds: float
    facility_id: UUID | None = None
    cloud_state: Literal["NOT_CONFIGURED", "CONNECTED", "OFFLINE", "CONFLICT"] = "NOT_CONFIGURED"
    sync_state: Literal["NOT_CONFIGURED", "PENDING", "SYNCHRONIZED", "CONFLICT"] = "NOT_CONFIGURED"
    components: list[ComponentHealth]


class LogRecord(Contract):
    timestamp: datetime
    level: Literal["INFO", "WARNING", "ERROR"]
    component: Literal["edge-runtime"] = "edge-runtime"
    event: str
    request_id: UUID | None = None
    outcome: Literal["success", "denied", "failure"]
    duration_ms: float | None = None


class Diagnostics(Contract):
    schema_version: Literal["1"] = "1"
    health: RuntimeHealth
    logs: list[LogRecord]
    log_capacity: int
    discarded_log_count: int
    redaction: Literal["allowlisted-fields-only"] = "allowlisted-fields-only"


class RuntimeErrorResponse(Contract):
    code: str
    message: str
    details: dict[str, str]
    request_id: UUID
