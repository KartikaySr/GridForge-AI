from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from edge.runtime.contracts import Contract

Stream = Literal[
    "telemetry", "registry", "intelligence", "optimization", "dispatch", "finance", "ai"
]


class SyncEntry(Contract):
    sequence: int = Field(gt=0)
    event_id: UUID
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    body: dict[str, Any]


class SyncBatch(Contract):
    schema_version: Literal["1"] = "1"
    edge_id: UUID
    stream: Stream
    entries: list[SyncEntry] = Field(min_length=1, max_length=20)


class SyncAck(Contract):
    schema_version: Literal["1"] = "1"
    edge_id: UUID
    stream: Stream
    acknowledged_sequence: int = Field(ge=0)
    accepted: int = Field(ge=0)
    replayed: int = Field(ge=0)
    committed_at: datetime


class CloudStreamCursor(Contract):
    stream: Stream
    acknowledged_sequence: int = Field(ge=0)


class CloudSyncState(Contract):
    schema_version: Literal["1"] = "1"
    edge_id: UUID
    org_id: UUID
    facility_id: UUID
    observed_at: datetime
    cursors: list[CloudStreamCursor]
    mode: Literal["SIMULATION"] = "SIMULATION"


class SyncConflict(Contract):
    id: int
    stream: Stream
    sequence: int
    code: str
    detected_at: datetime
    detail: str
    resolved: bool


class SyncStreamStatus(Contract):
    stream: Stream
    local_last_sequence: int
    acknowledged_sequence: int
    pending_count: int
    oldest_pending_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    conflict_code: str | None


class SyncSnapshot(Contract):
    schema_version: Literal["1"] = "1"
    mode: Literal["SIMULATION"] = "SIMULATION"
    edge_id: UUID
    org_id: UUID
    facility_id: UUID
    observed_at: datetime
    state: Literal["NOT_CONFIGURED", "OFFLINE", "SYNCING", "SYNCHRONIZED", "CONFLICT"]
    configured: bool
    pending_count: int
    oldest_pending_at: datetime | None
    oldest_pending_age_seconds: float | None
    last_success_at: datetime | None
    conflict_count: int
    streams: list[SyncStreamStatus]
    conflicts: list[SyncConflict]
    message: str
