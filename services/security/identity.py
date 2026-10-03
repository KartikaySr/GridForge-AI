import hashlib
import secrets
import time
from datetime import UTC, datetime, timedelta
from threading import RLock
from uuid import UUID, uuid4

from edge.storage.repository import Repository
from services.dispatch.permissions import PermissionDenied, Principal
from services.security.audit import AuditService
from services.security.contracts import IdentityStatus, LocalUser, Login, UserChange, UserWrite
from services.security.policy import ROLES


def password_hash(password: str, salt: str) -> str:
    return hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), n=2**17, r=8, p=1, maxmem=256 * 1024 * 1024
    ).hex()


class IdentityRejected(ValueError):
    pass


class IdentityService:
    def __init__(self, repo: Repository, audit: AuditService, instance_id: UUID) -> None:
        self.repo, self.audit, self.instance_id = repo, audit, instance_id
        self.session: str | None = None
        self.lock = RLock()
        self.attempts: list[float] = []
        self.dummy_salt = secrets.token_hex(16)

    def users(self) -> list[LocalUser]:
        with self.repo.lock:
            return [
                LocalUser(
                    id=row["id"],
                    username=row["username"],
                    role=row["role"],
                    enabled=bool(row["enabled"]),
                    revision=row["revision"],
                )
                for row in self.repo.db.execute(
                    "SELECT id,username,role,enabled,revision FROM local_users ORDER BY username"
                )
            ]

    def current(self) -> Principal | None:
        if self.session is None:
            return None
        with self.repo.lock:
            row = self.repo.db.execute(
                "SELECT u.*,s.expires_at,s.user_revision,s.revoked FROM local_sessions s "
                "JOIN local_users u ON u.id=s.user_id WHERE s.id=? AND s.instance_id=?",
                (self.session, str(self.instance_id)),
            ).fetchone()
        if (
            not row
            or row["revoked"]
            or not row["enabled"]
            or row["revision"] != row["user_revision"]
        ):
            return None
        expiry = datetime.fromisoformat(row["expires_at"])
        if datetime.now(UTC) >= expiry:
            return None
        return Principal(
            row["id"], self.repo.org_id, self.repo.facility_id, ROLES[row["role"]], expiry
        )

    def status(self) -> IdentityStatus:
        principal = self.current()
        users = self.users()
        user = next((u for u in users if str(u.id) == principal.actor), None) if principal else None
        return IdentityStatus(
            setup_required=not users,
            authenticated=principal is not None,
            user=user,
            permissions=sorted(principal.permissions) if principal else [],
            expires_at=principal.expires_at if principal else None,
        )

    def create(self, write: UserWrite, actor: Principal | None = None) -> LocalUser:
        with self.lock:
            users = self.users()
            if users:
                if actor is None:
                    raise PermissionDenied("BOOTSTRAP_CLOSED")
                actor.require(
                    "user.manage", self.repo.org_id, self.repo.facility_id, datetime.now(UTC)
                )
            elif write.role != "ORG_ADMIN":
                raise PermissionDenied("FIRST_USER_MUST_BE_ORG_ADMIN")
            if len(users) >= 100:
                raise IdentityRejected("USER_CAPACITY")
            if any(u.username == write.username.lower() for u in users):
                raise IdentityRejected("USERNAME_EXISTS")
            salt = secrets.token_hex(16)
            password = password_hash(write.password, salt)
            user = LocalUser(
                id=uuid4(),
                username=write.username.lower(),
                role=write.role,
                enabled=True,
                revision=1,
            )
            with self.repo.lock, self.repo.db:
                self.repo.db.execute(
                    "INSERT INTO local_users VALUES (?,?,?,?,?,1,1,?)",
                    (
                        str(user.id),
                        user.username,
                        password,
                        salt,
                        user.role,
                        datetime.now(UTC).isoformat(),
                    ),
                )
                self.audit.record(
                    "identity.created", "success", actor.actor if actor else str(user.id)
                )
            return user

    def login(self, write: Login) -> IdentityStatus:
        with self.lock:
            now = time.monotonic()
            self.attempts = [value for value in self.attempts if now - value < 60]
            if len(self.attempts) >= 5:
                raise PermissionDenied("LOGIN_RATE_LIMITED")
            self.attempts.append(now)
            with self.repo.lock:
                row = self.repo.db.execute(
                    "SELECT * FROM local_users WHERE username=?", (write.username.lower(),)
                ).fetchone()
            candidate = password_hash(write.password, row["salt"] if row else self.dummy_salt)
            if (
                not row
                or not row["enabled"]
                or not secrets.compare_digest(row["password_hash"], candidate)
            ):
                self.audit.record("identity.login", "denied")
                raise PermissionDenied("LOGIN_FAILED")
            self.logout()
            with self.repo.lock, self.repo.db:
                session = secrets.token_hex(32)
                self.repo.db.execute(
                    "INSERT INTO local_sessions VALUES (?,?,?,?,?,0)",
                    (
                        session,
                        row["id"],
                        row["revision"],
                        str(self.instance_id),
                        (datetime.now(UTC) + timedelta(hours=8)).isoformat(),
                    ),
                )
                self.audit.record("identity.login", "success", row["id"])
                self.session = session
            self.attempts.clear()
            return self.status()

    def logout(self) -> IdentityStatus:
        with self.lock, self.repo.lock, self.repo.db:
            if self.session:
                principal = self.current()
                self.repo.db.execute(
                    "UPDATE local_sessions SET revoked=1 WHERE id=?", (self.session,)
                )
                self.session = None
                try:
                    self.audit.record(
                        "identity.logout", "success", principal.actor if principal else "expired"
                    )
                except ValueError:
                    # Revocation must remain available even when the audit store fails closed.
                    self.audit.integrity_ok = False
            self.session = None
        return self.status()

    def change(self, write: UserChange, actor: Principal) -> LocalUser:
        actor.require("user.manage", self.repo.org_id, self.repo.facility_id, datetime.now(UTC))
        with self.lock, self.repo.lock, self.repo.db:
            users = self.users()
            prior = next((u for u in users if u.id == write.user_id), None)
            if prior is None or prior.revision != write.expected_revision:
                raise IdentityRejected("USER_REVISION_CONFLICT")
            if (
                prior.role in {"ORG_ADMIN", "SUPER_ADMIN"}
                and (not write.enabled or write.role not in {"ORG_ADMIN", "SUPER_ADMIN"})
                and sum(u.enabled and u.role in {"ORG_ADMIN", "SUPER_ADMIN"} for u in users) <= 1
            ):
                raise IdentityRejected("LAST_ADMIN_REQUIRED")
            self.repo.db.execute(
                "UPDATE local_users SET role=?,enabled=?,revision=revision+1 WHERE id=?",
                (write.role, int(write.enabled), str(write.user_id)),
            )
            self.repo.db.execute(
                "UPDATE local_sessions SET revoked=1 WHERE user_id=?", (str(write.user_id),)
            )
            self.audit.record("identity.changed", "success", actor.actor)
            return prior.model_copy(
                update={
                    "role": write.role,
                    "enabled": write.enabled,
                    "revision": prior.revision + 1,
                }
            )
