from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from services.security.policy import ALL


class PermissionDenied(ValueError):
    pass


@dataclass(frozen=True)
class Principal:
    """Provisioned by trusted composition, never populated from an HTTP body/header role."""

    actor: str
    org_id: UUID
    facility_id: UUID
    permissions: frozenset[str]
    expires_at: datetime

    def require(self, permission: str, org_id: UUID, facility_id: UUID, now: datetime) -> None:
        if (self.org_id, self.facility_id) != (org_id, facility_id):
            raise PermissionDenied("SCOPE_DENIED")
        if now >= self.expires_at or permission not in self.permissions:
            raise PermissionDenied("PERMISSION_DENIED_OR_SESSION_EXPIRED")


SIMULATION_PERMISSIONS = ALL
