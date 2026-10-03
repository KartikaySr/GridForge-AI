from datetime import datetime
from uuid import UUID

from pydantic import Field

from edge.runtime.contracts import Contract
from services.security.policy import Role


class Login(Contract):
    username: str = Field(pattern=r"^[a-zA-Z0-9_.-]{3,50}$")
    password: str = Field(min_length=12, max_length=128, repr=False)


class UserWrite(Login):
    role: Role


class UserChange(Contract):
    user_id: UUID
    role: Role
    enabled: bool
    expected_revision: int = Field(ge=1)


class LocalUser(Contract):
    id: UUID
    username: str
    role: Role
    enabled: bool
    revision: int


class IdentityStatus(Contract):
    setup_required: bool
    authenticated: bool
    user: LocalUser | None
    permissions: list[str]
    expires_at: datetime | None
    mode: str = "SIMULATION"


class AuditRow(Contract):
    sequence: int
    event_id: UUID
    occurred_at: datetime
    actor: str
    action: str
    outcome: str
    request_id: UUID
    correlation_id: UUID
    previous_hash: str
    digest: str


class AuditSnapshot(Contract):
    integrity_ok: bool
    count: int
    head: str
    rows: list[AuditRow]


class Metric(Contract):
    route: str
    requests: int
    failures: int
    duration_ms_total: float
    duration_ms_max: float


class OperationsSnapshot(Contract):
    observed_at: datetime
    requests: list[Metric]
    counters: dict[str, int]
    schema_version: int
    audit_integrity_ok: bool
