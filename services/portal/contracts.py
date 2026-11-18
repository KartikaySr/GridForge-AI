from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from edge.runtime.contracts import Contract
from services.sync.contracts import Stream


class PortalLogin(Contract):
    username: str = Field(pattern=r"^[a-zA-Z0-9_.-]{3,64}$")
    password: str = Field(min_length=12, max_length=128)


class PortalIdentity(Contract):
    id: UUID
    username: str
    permission: Literal["portfolio.read"] = "portfolio.read"
    expires_at: datetime


class PortalFacility(Contract):
    edge_id: UUID
    org_id: UUID
    facility_id: UUID
    enabled: bool
    last_received_at: datetime | None
    freshness: Literal["RECENT_RECEIPT", "STALE", "NO_DATA"]


class Portfolio(Contract):
    mode: Literal["SIMULATION"] = "SIMULATION"
    observed_at: datetime
    facilities: list[PortalFacility]
    limit: Literal[100] = 100


class PortalEvent(Contract):
    event_id: UUID
    sequence: int
    stream: Stream
    event_type: str
    received_at: datetime
    body: dict[str, Any]


class PortalHistory(Contract):
    mode: Literal["SIMULATION"] = "SIMULATION"
    observed_at: datetime
    edge_id: UUID
    stream: Stream
    events: list[PortalEvent]
    next_before: int | None


class MobileSession(Contract):
    token: str
    identity: PortalIdentity


class FieldReportWrite(Contract):
    request_id: UUID
    edge_id: UUID
    text: str = Field(min_length=1, max_length=2000, pattern=r"\S")


class FieldReportReceipt(Contract):
    request_id: UUID
    received_at: datetime
    status: Literal["accepted"] = "accepted"


class FieldReportRecord(FieldReportReceipt):
    edge_id: UUID
    text: str


class FieldReportHistory(Contract):
    edge_id: UUID
    mode: Literal["SIMULATION"] = "SIMULATION"
    reports: list[FieldReportRecord]
    limit: Literal[100] = 100
