from datetime import UTC, datetime

from edge.runtime.contracts import Diagnostics
from edge.storage.repository import Repository
from services.security.audit import AuditService
from services.security.contracts import Metric, OperationsSnapshot


class OperationsService:
    def __init__(self, repo: Repository, audit: AuditService) -> None:
        self.repo, self.audit = repo, audit

    def request(self, route: str, status: int, elapsed: float) -> None:
        with self.repo.lock, self.repo.db:
            self.repo.db.execute(
                "INSERT INTO runtime_metrics VALUES (?,1,?,?,?) ON CONFLICT(route) DO UPDATE SET "
                "requests=requests+1,failures=failures+excluded.failures,"
                "duration_ms_total=duration_ms_total+excluded.duration_ms_total,"
                "duration_ms_max=MAX(duration_ms_max,excluded.duration_ms_max)",
                (route, int(status >= 400), elapsed, elapsed),
            )

    def snapshot(self) -> OperationsSnapshot:
        with self.repo.lock:
            counters = {
                row[0]: row[1] for row in self.repo.db.execute("SELECT name,value FROM counters")
            }
            for key, table in [
                ("telemetry_rows", "telemetry"),
                ("predictions", "predictions"),
                ("commands", "dispatch_commands"),
                ("finance_entries", "finance_ledger"),
                ("ai_answers", "ai_answers"),
            ]:
                counters[key] = self.repo.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            metrics = [
                Metric(
                    route=row[0],
                    requests=row[1],
                    failures=row[2],
                    duration_ms_total=row[3],
                    duration_ms_max=row[4],
                )
                for row in self.repo.db.execute("SELECT * FROM runtime_metrics ORDER BY route")
            ]
            return OperationsSnapshot(
                observed_at=datetime.now(UTC),
                requests=metrics,
                counters=counters,
                schema_version=self.repo.db.execute("PRAGMA user_version").fetchone()[0],
                audit_integrity_ok=self.audit.integrity_ok,
            )

    def bundle(self, diagnostics: Diagnostics) -> dict[str, object]:
        # Explicit construction, no environment, filesystem paths, request bodies or documents.
        return {
            "format": "gridforge-diagnostics-v1",
            "mode": "SIMULATION",
            "created_at": datetime.now(UTC).isoformat(),
            "diagnostics": diagnostics.model_dump(mode="json"),
            "operations": self.snapshot().model_dump(mode="json"),
            "audit": {
                "integrity_ok": self.audit.verify(),
                "count": self.audit.snapshot().count,
                "head": self.audit.snapshot().head,
            },
        }
