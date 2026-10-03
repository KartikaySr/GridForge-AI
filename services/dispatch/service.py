import hashlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from edge.connectors.dispatch_simulator import DispatchSimulator
from edge.storage.repository import CapacityError, Rejected
from services.dispatch.contracts import (
    ApprovalRequest,
    DecisionRequest,
    DispatchAction,
    DispatchCommand,
    DispatchDetail,
    DispatchEvent,
    DispatchSnapshot,
    DispatchState,
    ValidationEvidence,
)
from services.dispatch.permissions import Principal
from services.forecasting.service import ForecastService
from services.optimization.contracts import OptimizationRun
from services.optimization.engine import evaluate
from services.registry.contracts import Asset

if TYPE_CHECKING:
    from edge.storage.repository import Repository

TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "REJECTED"}
TRANSITIONS: dict[str, set[str]] = {
    "PENDING_APPROVAL": {"APPROVED", "REJECTED", "CANCELLED", "FAILED"},
    "APPROVED": {"QUEUED", "CANCELLED", "FAILED"},
    "QUEUED": {"SENT", "CANCELLED", "FAILED"},
    "SENT": {"SENT", "ACKNOWLEDGED", "CANCELLED", "FAILED"},
    "ACKNOWLEDGED": {"EXECUTING", "CANCELLED", "FAILED"},
    "EXECUTING": {"COMPLETED", "CANCELLED", "FAILED"},
}


class DispatchService:
    capacity = 500

    def __init__(self, repo: "Repository", forecasting: ForecastService) -> None:
        self.repo, self.forecasting = repo, forecasting
        self.adapter = DispatchSimulator(repo)
        self.worker_error: str | None = None

    def require(self, principal: Principal, permission: str, now: datetime) -> None:
        principal.require(permission, self.repo.org_id, self.repo.facility_id, now)

    def load(self, command_id: UUID) -> DispatchCommand:
        row = self.repo.db.execute(
            "SELECT body FROM dispatch_commands WHERE id=?", (str(command_id),)
        ).fetchone()
        if not row:
            raise Rejected("COMMAND_NOT_FOUND")
        return DispatchCommand.model_validate_json(row[0])

    def run(self, run_id: UUID) -> OptimizationRun:
        row = self.repo.db.execute(
            "SELECT body FROM optimization_runs WHERE id=?", (str(run_id),)
        ).fetchone()
        if not row:
            raise Rejected("RUN_NOT_FOUND")
        return OptimizationRun.model_validate_json(row[0])

    def validate(
        self, run: OptimizationRun, now: datetime, unavailable: bool
    ) -> ValidationEvidence:
        snapshot = self.forecasting.snapshot(unavailable, now)
        _, _, _, _, digest = self.forecasting.context()
        if self.worker_error or snapshot.status != "READY" or snapshot.latest is None:
            raise Rejected("DISPATCH_INPUT_NOT_READY")
        if digest != run.registry_digest:
            raise Rejected("DISPATCH_CONFIGURATION_CHANGED")
        if snapshot.risk_assessment != "BREACH" or not run.proposal:
            raise Rejected("DISPATCH_NO_CURRENT_RISK_OR_PROPOSAL")
        end = now + timedelta(seconds=run.request.duration_seconds)
        policy = run.policy
        if (
            not policy.effective_from <= now < end <= policy.effective_until
            or end > snapshot.latest.values[-1].ends_at
        ):
            raise Rejected("DISPATCH_WINDOW_INVALID")
        records = self.repo.registry.records()
        if any(
            not r.entity.enabled for r in records if r.entity.kind in ("organization", "facility")
        ):
            raise Rejected("DISPATCH_SCOPE_DISABLED")
        points = {p.asset_id: p for p in self.repo.state()[1]}
        assets = {r.entity.id: r.entity for r in records if isinstance(r.entity, Asset)}
        selected = [c for c in run.candidates if c.selected_kw > 0]
        total = sum(c.selected_kw for c in selected)
        if (
            not selected
            or total > policy.max_total_reduction_kw
            or run.request.duration_seconds > policy.max_duration_seconds
        ):
            raise Rejected("DISPATCH_COMMAND_BOUNDS")
        for candidate in selected:
            asset = assets.get(candidate.asset_id)
            if asset is None:
                raise Rejected("DISPATCH_ASSET_MISSING")
            fresh = evaluate(asset, records, points.get(asset.id), policy, now, end)
            if not fresh.eligible or candidate.selected_kw > fresh.available_kw:
                raise Rejected("DISPATCH_HARD_CONSTRAINT")
        return ValidationEvidence(
            at=now,
            prediction_id=snapshot.latest.id,
            registry_digest=digest,
            telemetry_rows=[p.row_id for p in points.values()],
        )

    def persist(self, command: DispatchCommand) -> None:
        self.repo.db.execute(
            "UPDATE dispatch_commands SET state=?,body=? WHERE id=?",
            (command.state, command.model_dump_json(), str(command.id)),
        )

    def event(
        self,
        command: DispatchCommand,
        previous: DispatchState | None,
        actor: str,
        cause: UUID,
        kind: str,
    ) -> None:
        seq = self.repo.db.execute(
            "SELECT COALESCE(MAX(sequence),0)+1 FROM dispatch_outbox"
        ).fetchone()[0]
        event = DispatchEvent(
            sequence=seq,
            event_id=uuid4(),
            event_type=kind,
            occurred_at=command.updated_at,
            org_id=self.repo.org_id,
            facility_id=self.repo.facility_id,
            correlation_id=command.id,
            causation_id=cause,
            idempotency_key=uuid4(),
            actor=actor,
            command_id=command.id,
            revision=command.revision,
            from_state=previous,
            to_state=command.state,
            reason=command.reason,
        )
        self.repo.db.execute(
            "INSERT INTO dispatch_outbox(sequence,event_id,command_id,body) VALUES (?,?,?,?)",
            (seq, str(event.event_id), str(command.id), event.model_dump_json()),
        )

    def transition(
        self,
        command: DispatchCommand,
        target: DispatchState,
        reason: str,
        now: datetime,
        actor: str,
        cause: UUID,
        kind: str | None = None,
    ) -> None:
        if target not in TRANSITIONS.get(command.state, set()):
            raise Rejected("INVALID_DISPATCH_TRANSITION")
        previous = command.state
        command.state = target
        command.reason = reason
        command.updated_at = now
        command.revision += 1
        if target in TERMINAL:
            self.adapter.stop(command)
        self.persist(command)
        self.event(
            command, previous, actor, cause, kind or "Dispatch" + target.title().replace("_", "")
        )

    def replay(self, request_id: UUID, fingerprint: str) -> DispatchCommand | None:
        row = self.repo.db.execute(
            "SELECT fingerprint,response FROM dispatch_requests WHERE request_id=?",
            (str(request_id),),
        ).fetchone()
        if row:
            if row[0] != fingerprint:
                raise Rejected("IDEMPOTENCY_CONFLICT")
            return DispatchCommand.model_validate_json(row[1])
        if self.repo.db.execute("SELECT COUNT(*) FROM dispatch_requests").fetchone()[0] >= 5000:
            raise CapacityError("DISPATCH_REQUEST_CAPACITY")
        return None

    def receipt(self, request_id: UUID, fingerprint: str, command: DispatchCommand) -> None:
        self.repo.db.execute(
            "INSERT INTO dispatch_requests VALUES (?,?,?)",
            (str(request_id), fingerprint, command.model_dump_json()),
        )

    def request(
        self,
        write: ApprovalRequest,
        principal: Principal,
        unavailable: bool = False,
        now: datetime | None = None,
    ) -> DispatchCommand:
        now = now or datetime.now(UTC)
        self.require(principal, "dispatch.request", now)
        fingerprint = hashlib.sha256(
            (principal.actor + write.model_dump_json()).encode()
        ).hexdigest()
        with self.repo.lock, self.repo.db:
            replay = self.replay(write.request_id, fingerprint)
            if replay:
                return replay
            if self.repo.db.execute(
                "SELECT 1 FROM dispatch_commands WHERE run_id=?", (str(write.run_id),)
            ).fetchone():
                raise Rejected("PROPOSAL_ALREADY_REQUESTED")
            if (
                self.repo.db.execute("SELECT COUNT(*) FROM dispatch_commands").fetchone()[0]
                >= self.capacity
            ):
                raise CapacityError("DISPATCH_CAPACITY")
            if self.active():
                raise Rejected("DISPATCH_ALREADY_ACTIVE")
            run = self.run(write.run_id)
            validation = self.validate(run, now, unavailable)
            assert run.proposal
            command = DispatchCommand(
                id=uuid4(),
                run_id=run.id,
                proposal_id=run.proposal.id,
                org_id=self.repo.org_id,
                facility_id=self.repo.facility_id,
                revision=1,
                state="PENDING_APPROVAL",
                created_at=now,
                updated_at=now,
                approval_deadline=now + timedelta(seconds=120),
                behavior=write.behavior,
                actions=[
                    DispatchAction(asset_id=c.asset_id, reduction_kw=c.selected_kw)
                    for c in run.candidates
                    if c.selected_kw > 0
                ],
                duration_seconds=run.request.duration_seconds,
                reason="Explicit human simulation approval required within 120 seconds",
                validations=[validation],
            )
            self.repo.db.execute(
                "INSERT INTO dispatch_commands VALUES (?,?,?,?)",
                (str(command.id), str(run.id), command.state, command.model_dump_json()),
            )
            self.event(command, None, principal.actor, write.request_id, "ApprovalRequested")
            self.receipt(write.request_id, fingerprint, command)
            return command

    def decide(
        self,
        write: DecisionRequest,
        principal: Principal,
        unavailable: bool = False,
        now: datetime | None = None,
    ) -> DispatchCommand:
        now = now or datetime.now(UTC)
        self.require(
            principal, "dispatch.cancel" if write.action == "cancel" else "dispatch.approve", now
        )
        fingerprint = hashlib.sha256(
            (principal.actor + write.model_dump_json()).encode()
        ).hexdigest()
        with self.repo.lock, self.repo.db:
            replay = self.replay(write.request_id, fingerprint)
            if replay:
                return replay
            command = self.load(write.command_id)
            if command.revision != write.expected_revision:
                raise Rejected("DISPATCH_REVISION_CONFLICT")
            if write.action == "cancel":
                self.transition(
                    command, "CANCELLED", write.reason, now, principal.actor, write.request_id
                )
            else:
                if command.state != "PENDING_APPROVAL":
                    raise Rejected("INVALID_APPROVAL_STATE")
                if now >= command.approval_deadline:
                    self.transition(
                        command,
                        "REJECTED",
                        "APPROVAL_TIMEOUT",
                        now,
                        principal.actor,
                        write.request_id,
                    )
                elif write.action == "reject":
                    self.transition(
                        command,
                        "REJECTED",
                        write.reason,
                        now,
                        principal.actor,
                        write.request_id,
                        "ApprovalRejected",
                    )
                else:
                    try:
                        evidence = self.validate(self.run(command.run_id), now, unavailable)
                    except Rejected as exc:
                        self.transition(
                            command, "REJECTED", str(exc), now, principal.actor, write.request_id
                        )
                    else:
                        command.validations.append(evidence)
                        command.approved_by = principal.actor
                        command.approved_until = min(
                            principal.expires_at, now + timedelta(seconds=30)
                        )
                        self.transition(
                            command,
                            "APPROVED",
                            write.reason,
                            now,
                            principal.actor,
                            write.request_id,
                            "ApprovalGranted",
                        )
                        self.transition(
                            command,
                            "QUEUED",
                            "Awaiting simulator worker; fresh constraints required",
                            now,
                            principal.actor,
                            write.request_id,
                        )
            self.receipt(write.request_id, fingerprint, command)
            return command

    def active(self) -> list[DispatchCommand]:
        return [
            DispatchCommand.model_validate_json(r[0])
            for r in self.repo.db.execute(
                "SELECT body FROM dispatch_commands WHERE state NOT IN "
                "('COMPLETED','FAILED','CANCELLED','REJECTED')"
            )
        ]

    def recover(self, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        with self.repo.lock, self.repo.db:
            for command in self.active():
                self.transition(
                    command,
                    "FAILED",
                    "RUNTIME_RECOVERY_REQUIRES_NEW_PROPOSAL_AND_APPROVAL",
                    now,
                    "simulation-dispatch-worker",
                    command.id,
                )

    def tick(self, unavailable: bool = False, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        try:
            if self.worker_error:
                self.recover(now)
                self.worker_error = None
                return
            with self.repo.lock, self.repo.db:
                for command in self.active():
                    self.advance(command, unavailable, now)
        except Exception:
            # Next successful transaction fails outstanding work after an uncertain error.
            self.worker_error = "DISPATCH_WORKER_OR_STORAGE_FAILED"

    def advance(self, command: DispatchCommand, unavailable: bool, now: datetime) -> None:
        actor = "simulation-dispatch-worker"

        def move(target: DispatchState, reason: str, kind: str | None = None) -> None:
            self.transition(command, target, reason, now, actor, command.id, kind)

        if now < command.updated_at:
            move("FAILED", "CLOCK_MOVED_BACKWARDS")
            return
        if command.state == "PENDING_APPROVAL":
            if now >= command.approval_deadline:
                move("REJECTED", "APPROVAL_TIMEOUT")
            return
        if command.state == "EXECUTING":
            if (
                command.last_guard_at is None
                or not 0 <= (now - command.last_guard_at).total_seconds() <= 5
            ):
                move("FAILED", "EXECUTION_MONITORING_GAP")
                return
            command.last_guard_at = now
            self.persist(command)
            if command.execution_ends_at and now >= command.execution_ends_at:
                move(
                    "COMPLETED",
                    "Simulator duration elapsed; measured verification is a separate phase",
                )
                return
            run = self.run(command.run_id)
            _, _, _, _, digest = self.forecasting.context()
            if (
                unavailable
                or digest != run.registry_digest
                or self.forecasting.live_reason(now, unavailable)
            ):
                move("FAILED", "EXECUTION_INPUT_OR_CONFIGURATION_CHANGED")
                return
            records = self.repo.registry.records()
            points = {p.asset_id: p for p in self.repo.state()[1]}
            for record in records:
                asset = record.entity
                if isinstance(asset, Asset) and asset.id in {a.asset_id for a in command.actions}:
                    point = points.get(asset.id)
                    if point is None or not asset.min_load_kw <= point.value <= asset.max_load_kw:
                        move("FAILED", "EXECUTION_LOAD_BOUND")
                        return
            return
        if not command.approved_by or not command.approved_until or now >= command.approved_until:
            move("FAILED", "APPROVAL_EXECUTION_WINDOW_EXPIRED")
            return
        try:
            validation = self.validate(self.run(command.run_id), now, unavailable)
        except Rejected as exc:
            move("FAILED", str(exc))
            return
        if command.state == "QUEUED":
            command.validations.append(validation)
            command.attempts += 1
            command.sent_at = now
            self.adapter.send(command, now)
            move("SENT", "Simulator accepted immutable command envelope; awaiting ACK")
        elif command.state == "SENT":
            if command.behavior == "failed_command":
                move("FAILED", "SIMULATOR_COMMAND_REJECTED")
            elif self.adapter.acknowledged(command, now):
                command.acknowledged_at = now
                move("ACKNOWLEDGED", "Durable simulator ACK received")
            elif (
                command.sent_at
                and (now - command.sent_at).total_seconds() >= command.ack_timeout_seconds
            ):
                if command.attempts >= command.max_attempts:
                    move("FAILED", "ACK_TIMEOUT; no execution assumed")
                else:
                    command.attempts += 1
                    command.sent_at = now
                    self.adapter.send(command, now)
                    move("SENT", "Retry same command ID after ACK timeout", "DispatchRetried")
        elif command.state == "ACKNOWLEDGED":
            command.validations.append(validation)
            command.last_guard_at = now
            command.execution_started_at = now
            command.execution_ends_at = now + timedelta(seconds=command.duration_seconds)
            self.adapter.start(command, now)
            move("EXECUTING", "Simulated load reduction active; not verified savings")

    def events(self, after: int = 0, command_id: UUID | None = None) -> list[DispatchEvent]:
        with self.repo.lock:
            return [
                DispatchEvent.model_validate_json(r[0])
                for r in self.repo.db.execute(
                    (
                        "SELECT body FROM dispatch_outbox WHERE sequence>? "
                        "AND (? IS NULL OR command_id=?) ORDER BY sequence LIMIT 100"
                    ),
                    (
                        after,
                        str(command_id) if command_id else None,
                        str(command_id) if command_id else None,
                    ),
                )
            ]

    def detail(
        self, command_id: UUID, principal: Principal, now: datetime | None = None
    ) -> DispatchDetail:
        self.require(principal, "dispatch.read", now or datetime.now(UTC))
        with self.repo.lock:
            return DispatchDetail(
                command=self.load(command_id), timeline=self.events(command_id=command_id)
            )

    def snapshot(self, principal: Principal, now: datetime | None = None) -> DispatchSnapshot:
        now = now or datetime.now(UTC)
        self.require(principal, "dispatch.read", now)
        with self.repo.lock:
            facility = self.forecasting.context()[0]
            return DispatchSnapshot(
                observed_at=now,
                timezone=facility.timezone,
                actor=principal.actor,
                permissions=sorted(principal.permissions),
                session_expires_at=principal.expires_at,
                commands=[
                    DispatchCommand.model_validate_json(r[0])
                    for r in self.repo.db.execute(
                        "SELECT body FROM dispatch_commands ORDER BY rowid DESC LIMIT 20"
                    )
                ],
                pending_events=self.repo.db.execute(
                    "SELECT COUNT(*) FROM dispatch_outbox WHERE acknowledged=0"
                ).fetchone()[0],
                command_count=self.repo.db.execute(
                    "SELECT COUNT(*) FROM dispatch_commands"
                ).fetchone()[0],
                capacity=self.capacity,
                worker_error=self.worker_error,
            )
