import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from edge.storage.repository import Repository
from services.security.contracts import AuditRow, AuditSnapshot


def chain_hash(previous: str, body: str) -> str:
    return hashlib.sha256((previous + body).encode()).hexdigest()


class AuditService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo
        self.integrity_ok = self.verify()

    def verify(self) -> bool:
        head = "0" * 64
        with self.repo.lock:
            for index, row in enumerate(
                self.repo.db.execute(
                    "SELECT sequence,body,previous_hash,digest FROM security_audit "
                    "ORDER BY sequence"
                ),
                1,
            ):
                if row[0] != index or row[2] != head or chain_hash(head, row[1]) != row[3]:
                    return False
                head = row[3]
        return True

    def record(
        self,
        action: str,
        outcome: str,
        actor: str = "anonymous",
        request_id: UUID | None = None,
        correlation_id: UUID | None = None,
    ) -> None:
        if not self.integrity_ok:
            raise ValueError("AUDIT_INTEGRITY_FAILURE")
        with self.repo.lock, self.repo.db:
            row = self.repo.db.execute(
                "SELECT sequence,digest FROM security_audit ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            if row and row[0] >= 100000:
                raise ValueError("AUDIT_CAPACITY_REACHED")
            previous = row[1] if row else "0" * 64
            request_id = request_id or uuid4()
            event_id = uuid4()
            body = json.dumps(
                {
                    "event_id": str(event_id),
                    "occurred_at": datetime.now(UTC).isoformat(),
                    "actor": actor,
                    "action": action,
                    "outcome": outcome,
                    "request_id": str(request_id),
                    "correlation_id": str(correlation_id or request_id),
                    "org_id": str(self.repo.org_id),
                    "facility_id": str(self.repo.facility_id),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            self.repo.db.execute(
                "INSERT INTO security_audit(event_id,body,previous_hash,digest) VALUES (?,?,?,?)",
                (str(event_id), body, previous, chain_hash(previous, body)),
            )

    def snapshot(self, after: int = 0) -> AuditSnapshot:
        with self.repo.lock:
            head = self.repo.db.execute(
                "SELECT digest FROM security_audit ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            rows = []
            for row in self.repo.db.execute(
                "SELECT * FROM security_audit WHERE sequence>? ORDER BY sequence LIMIT 100",
                (after,),
            ):
                body = json.loads(row["body"])
                body.pop("org_id")
                body.pop("facility_id")
                rows.append(
                    AuditRow.model_validate(
                        body
                        | {
                            "sequence": row["sequence"],
                            "previous_hash": row["previous_hash"],
                            "digest": row["digest"],
                        }
                    )
                )
            self.integrity_ok = self.verify()
            return AuditSnapshot(
                integrity_ok=self.integrity_ok,
                count=self.repo.db.execute("SELECT COUNT(*) FROM security_audit").fetchone()[0],
                head=head[0] if head else "0" * 64,
                rows=rows,
            )
