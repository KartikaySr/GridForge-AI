import asyncio
import hashlib
from contextlib import suppress
from datetime import UTC, datetime
from uuid import uuid4

from edge.storage.repository import CapacityError, Rejected, Repository
from services.alerting.contracts import Incident, IncidentAction, IncidentSnapshot
from services.dispatch.permissions import Principal
from services.forecasting.contracts import IntelligenceEvent, RiskRecord


class IncidentService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo
        self.worker_error: str | None = None

    def save(self, incident: Incident, event_type: str) -> None:
        if self.repo.db.execute("SELECT COUNT(*) FROM incident_history").fetchone()[0] >= 20000:
            raise CapacityError("INCIDENT_HISTORY_CAPACITY")
        self.repo.db.execute(
            "INSERT INTO incidents(id,risk_id,body) VALUES (?,?,?) "
            "ON CONFLICT(risk_id) DO UPDATE SET body=excluded.body",
            (str(incident.id), str(incident.risk_id), incident.model_dump_json()),
        )
        self.repo.db.execute(
            "INSERT INTO incident_history(incident_id,event_type,body) VALUES (?,?,?)",
            (str(incident.id), event_type, incident.model_dump_json()),
        )

    def tick(self) -> None:
        with self.repo.lock, self.repo.db:
            cursor = self.repo.db.execute("SELECT sequence FROM incident_cursor").fetchone()[0]
            rows = self.repo.db.execute(
                "SELECT sequence,body FROM intelligence_outbox WHERE sequence>? "
                "ORDER BY sequence LIMIT 100",
                (cursor,),
            ).fetchall()
            for sequence, body in rows:
                event = IntelligenceEvent.model_validate_json(body)
                if event.org_id != self.repo.org_id or event.facility_id != self.repo.facility_id:
                    raise Rejected("INCIDENT_SOURCE_SCOPE")
                risk = event.payload
                if isinstance(risk, RiskRecord):
                    old = self.repo.db.execute(
                        "SELECT body FROM incidents WHERE risk_id=?", (str(risk.id),)
                    ).fetchone()
                    prior = Incident.model_validate_json(old[0]) if old else None
                    incident = Incident(
                        org_id=self.repo.org_id,
                        facility_id=self.repo.facility_id,
                        id=prior.id if prior else uuid4(),
                        risk_id=risk.id,
                        revision=prior.revision + 1 if prior else 1,
                        source_state=risk.state,
                        status=prior.status if prior else "OPEN",
                        opened_at=risk.opened_at,
                        updated_at=risk.updated_at,
                        prediction_id=risk.latest_prediction_id,
                        threshold_kw=risk.threshold_kw,
                        predicted_peak_kw=risk.predicted_peak_kw,
                        actor=prior.actor if prior else None,
                        note=prior.note if prior else None,
                    )
                    # A fresh active source can never remain manually resolved.
                    if risk.state == "OPEN" and incident.status == "CLOSED":
                        incident.status = "OPEN"
                    self.save(incident, event.event_type)
                self.repo.db.execute("UPDATE incident_cursor SET sequence=?", (sequence,))

    async def run(self) -> None:
        while True:
            job = asyncio.create_task(asyncio.to_thread(self.tick))
            try:
                await asyncio.shield(job)
                self.worker_error = None
            except asyncio.CancelledError:
                with suppress(Exception):
                    await job
                raise
            except Exception:
                self.worker_error = "INCIDENT_PROCESSING_FAILED"
            await asyncio.sleep(1)

    def act(self, write: IncidentAction, actor: Principal) -> Incident:
        actor.require("alert.manage", self.repo.org_id, self.repo.facility_id, datetime.now(UTC))
        fingerprint = hashlib.sha256(write.model_dump_json().encode()).hexdigest()
        with self.repo.lock, self.repo.db:
            old = self.repo.db.execute(
                "SELECT fingerprint,body FROM incident_requests WHERE request_id=?",
                (str(write.request_id),),
            ).fetchone()
            if old:
                if old[0] != fingerprint:
                    raise Rejected("INCIDENT_REQUEST_CONFLICT")
                return Incident.model_validate_json(old[1])
            row = self.repo.db.execute(
                "SELECT body FROM incidents WHERE id=?", (str(write.incident_id),)
            ).fetchone()
            if not row:
                raise Rejected("INCIDENT_NOT_FOUND")
            incident = Incident.model_validate_json(row[0])
            if incident.revision != write.expected_revision:
                raise Rejected("INCIDENT_REVISION_CONFLICT")
            if write.action == "acknowledge":
                if incident.status != "OPEN":
                    raise Rejected("INCIDENT_INVALID_TRANSITION")
                incident.status = "ACKNOWLEDGED"
            else:
                source = self.repo.db.execute(
                    "SELECT body FROM risks WHERE id=?", (str(incident.risk_id),)
                ).fetchone()
                if not source or RiskRecord.model_validate_json(source[0]).state == "OPEN":
                    raise Rejected("INCIDENT_SOURCE_STILL_ACTIVE")
                if incident.status != "ACKNOWLEDGED" or incident.source_state == "OPEN":
                    raise Rejected("INCIDENT_INVALID_TRANSITION")
                incident.status = "CLOSED"
            incident.revision += 1
            incident.updated_at = datetime.now(UTC)
            incident.actor, incident.note = actor.actor, write.note
            self.save(incident, write.action)
            self.repo.db.execute(
                "INSERT INTO incident_requests VALUES (?,?,?)",
                (str(write.request_id), fingerprint, incident.model_dump_json()),
            )
            return incident

    def snapshot(self, actor: Principal, before: int | None = None) -> IncidentSnapshot:
        actor.require("alert.read", self.repo.org_id, self.repo.facility_id, datetime.now(UTC))
        with self.repo.lock:
            cursor = self.repo.db.execute("SELECT sequence FROM incident_cursor").fetchone()[0]
            rows = self.repo.db.execute(
                "SELECT sequence,body FROM incidents WHERE sequence<? "
                "ORDER BY sequence DESC LIMIT 20",
                (before or 2**63 - 1,),
            ).fetchall()
            return IncidentSnapshot(
                observed_at=datetime.now(UTC),
                incidents=[Incident.model_validate_json(r[1]) for r in rows],
                worker_error=self.worker_error,
                processed_sequence=cursor,
                pending_events=self.repo.db.execute(
                    "SELECT COUNT(*) FROM intelligence_outbox WHERE sequence>?", (cursor,)
                ).fetchone()[0],
                total=self.repo.db.execute("SELECT COUNT(*) FROM incidents").fetchone()[0],
                next_before=rows[-1][0] if len(rows) == 20 else None,
            )
