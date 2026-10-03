import hashlib
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

from edge.storage.repository import CapacityError, Rejected
from services.dispatch.contracts import DispatchCommand
from services.dispatch.permissions import Principal
from services.finance.contracts import (
    DemandChargeAssessment,
    FinanceEvent,
    FinanceSnapshot,
    LedgerEntry,
    TariffVersion,
    TariffWrite,
    Verification,
    VerificationRequest,
)
from services.finance.engine import measure, rate_at, slots
from services.forecasting.contracts import Prediction
from services.optimization.contracts import OptimizationRun

if TYPE_CHECKING:
    from edge.storage.repository import Repository

CENT = Decimal("0.01")


class FinanceService:
    tariff_capacity = 100
    verification_capacity = 500

    def __init__(self, repo: "Repository") -> None:
        self.repo = repo
        self.worker_error: str | None = None

    def require(self, principal: Principal, permission: str, now: datetime) -> None:
        principal.require(permission, self.repo.org_id, self.repo.facility_id, now)

    def event(
        self,
        kind: Literal[
            "TariffVersionCreated",
            "VerificationStarted",
            "VerificationCompleted",
            "VerificationIncomplete",
            "SavingsEstimated",
            "SavingsVerified",
        ],
        resource: UUID,
        cause: UUID,
        actor: str,
        now: datetime,
    ) -> None:
        seq = self.repo.db.execute(
            "SELECT COALESCE(MAX(sequence),0)+1 FROM finance_outbox"
        ).fetchone()[0]
        envelope = FinanceEvent(
            sequence=seq,
            event_id=uuid4(),
            event_type=kind,
            occurred_at=now,
            org_id=self.repo.org_id,
            facility_id=self.repo.facility_id,
            actor=actor,
            correlation_id=resource,
            causation_id=cause,
            idempotency_key=uuid4(),
            resource_id=resource,
        )
        self.repo.db.execute(
            "INSERT INTO finance_outbox(sequence,event_id,body) VALUES (?,?,?)",
            (seq, str(envelope.event_id), envelope.model_dump_json()),
        )

    def tariff(
        self, write: TariffWrite, principal: Principal, now: datetime | None = None
    ) -> TariffVersion:
        now = now or datetime.now(UTC)
        self.require(principal, "tariff.update", now)
        fingerprint = hashlib.sha256(
            (principal.actor + write.model_dump_json()).encode()
        ).hexdigest()
        with self.repo.lock, self.repo.db:
            row = self.repo.db.execute(
                "SELECT fingerprint,body FROM finance_tariffs WHERE request_id=?",
                (str(write.request_id),),
            ).fetchone()
            if row:
                if row[0] != fingerprint:
                    raise Rejected("IDEMPOTENCY_CONFLICT")
                return TariffVersion.model_validate_json(row[1])
            if (
                self.repo.db.execute("SELECT COUNT(*) FROM finance_tariffs").fetchone()[0]
                >= self.tariff_capacity
            ):
                raise CapacityError("TARIFF_CAPACITY")
            version = TariffVersion(
                **write.tariff.model_dump(),
                id=uuid4(),
                org_id=self.repo.org_id,
                facility_id=self.repo.facility_id,
                created_at=now,
            )
            self.repo.db.execute(
                "INSERT INTO finance_tariffs VALUES (?,?,?,?)",
                (str(version.id), str(write.request_id), fingerprint, version.model_dump_json()),
            )
            self.event("TariffVersionCreated", version.id, write.request_id, principal.actor, now)
            return version

    def start(
        self, write: VerificationRequest, principal: Principal, now: datetime | None = None
    ) -> Verification:
        now = now or datetime.now(UTC)
        self.require(principal, "finance.verify", now)
        fingerprint = hashlib.sha256(
            (principal.actor + write.model_dump_json()).encode()
        ).hexdigest()
        with self.repo.lock, self.repo.db:
            row = self.repo.db.execute(
                "SELECT fingerprint,body FROM finance_verifications WHERE request_id=?",
                (str(write.request_id),),
            ).fetchone()
            if row:
                if row[0] != fingerprint:
                    raise Rejected("IDEMPOTENCY_CONFLICT")
                return Verification.model_validate_json(row[1])
            if (
                self.repo.db.execute("SELECT COUNT(*) FROM finance_verifications").fetchone()[0]
                >= self.verification_capacity
            ):
                raise CapacityError("VERIFICATION_CAPACITY")
            if self.repo.db.execute(
                "SELECT 1 FROM finance_verifications WHERE command_id=?", (str(write.command_id),)
            ).fetchone():
                raise Rejected("COMMAND_ALREADY_VERIFIED_OR_PENDING")
            command_row = self.repo.db.execute(
                "SELECT body FROM dispatch_commands WHERE id=?", (str(write.command_id),)
            ).fetchone()
            tariff_row = self.repo.db.execute(
                "SELECT body FROM finance_tariffs WHERE id=?", (str(write.tariff_id),)
            ).fetchone()
            if not command_row or not tariff_row:
                raise Rejected("COMMAND_OR_TARIFF_NOT_FOUND")
            command = DispatchCommand.model_validate_json(command_row[0])
            if (
                command.state != "COMPLETED"
                or command.execution_started_at is None
                or command.execution_ends_at is None
            ):
                raise Rejected("COMMAND_NOT_COMPLETED")
            tariff = TariffVersion.model_validate_json(tariff_row[0])
            run_row = self.repo.db.execute(
                "SELECT body FROM optimization_runs WHERE id=?", (str(command.run_id),)
            ).fetchone()
            if not run_row:
                raise Rejected("RUN_NOT_FOUND")
            run = OptimizationRun.model_validate_json(run_row[0])
            prediction_row = self.repo.db.execute(
                "SELECT body FROM predictions WHERE id=?", (str(run.prediction_id),)
            ).fetchone()
            if not prediction_row:
                raise Rejected("PREDICTION_NOT_FOUND")
            prediction = Prediction.model_validate_json(prediction_row[0])
            if prediction.created_at > command.execution_started_at or not prediction.values:
                raise Rejected("INVALID_PRE_DISPATCH_BASELINE")
            baseline = Decimal(str(prediction.values[0].value_kw))
            if baseline <= 0:
                raise Rejected("BASELINE_NOT_POSITIVE")
            start = command.execution_started_at
            end = command.execution_ends_at
            rebound_end = end + (end - start)
            assessment = DemandChargeAssessment(
                billing_period_start=tariff.billing_period_start,
                billing_period_end=tariff.billing_period_end,
                rate_per_kw=tariff.demand_charge_rate_per_kw,
            )
            case = Verification(
                id=uuid4(),
                request=write,
                org_id=self.repo.org_id,
                facility_id=self.repo.facility_id,
                status="PENDING",
                created_at=now,
                evaluated_at=None,
                command_id=command.id,
                run_id=run.id,
                proposal_id=command.proposal_id,
                prediction_id=prediction.id,
                baseline_kw=baseline,
                tariff=tariff,
                execution=None,
                rebound=None,
                expected_reduction_kw=Decimal(str(sum(a.reduction_kw for a in command.actions))),
                measured_reduction_kw=None,
                rebound_kwh=None,
                net_energy_kwh=None,
                gross_avoided_cost=None,
                rebound_cost=None,
                net_energy_value=None,
                demand_charge=assessment,
                reason="Awaiting complete execution and rebound telemetry through "
                + rebound_end.isoformat(),
            )
            self.repo.db.execute(
                "INSERT INTO finance_verifications VALUES (?,?,?,?,?,?)",
                (
                    str(case.id),
                    str(command.id),
                    str(write.request_id),
                    fingerprint,
                    case.status,
                    case.model_dump_json(),
                ),
            )
            self.event("VerificationStarted", case.id, write.request_id, principal.actor, now)
            # A tariff-versioned estimate is immutable and distinct from later measured value.
            estimate = self._estimated_cost(case, command)
            if estimate is not None:
                self.ledger(
                    case,
                    "ESTIMATED",
                    estimate,
                    "tariff-expected-curtailment-v1",
                    hashlib.sha256(
                        (run.model_dump_json() + tariff.model_dump_json()).encode()
                    ).hexdigest(),
                    "SIMULATED estimate from approved action; no measured actuals or rebound",
                    now,
                )
                self.event("SavingsEstimated", case.id, write.request_id, principal.actor, now)
            # A late request may be resolved immediately, under the same transaction.
            if now >= rebound_end + timedelta(seconds=5):
                self._evaluate(case, command, prediction, now)
            return case

    def _estimated_cost(self, case: Verification, command: DispatchCommand) -> Decimal | None:
        if not command.execution_started_at or not command.execution_ends_at:
            return None
        amount = Decimal(0)
        for second in slots(command.execution_started_at, command.execution_ends_at):
            rate = rate_at(case.tariff, second)
            if rate is None:
                return None
            amount += case.expected_reduction_kw * rate / Decimal(3600)
        return amount.quantize(CENT, rounding=ROUND_HALF_UP)

    def ledger(
        self,
        case: Verification,
        status: Literal["ESTIMATED", "VERIFIED"],
        amount: Decimal,
        method: str,
        digest: str,
        note: str,
        now: datetime,
    ) -> None:
        seq = self.repo.db.execute(
            "SELECT COALESCE(MAX(sequence),0)+1 FROM finance_ledger"
        ).fetchone()[0]
        entry = LedgerEntry(
            sequence=seq,
            id=uuid4(),
            status=status,
            occurred_at=now,
            org_id=self.repo.org_id,
            facility_id=self.repo.facility_id,
            verification_id=case.id,
            command_id=case.command_id,
            tariff_id=case.tariff.id,
            currency=case.tariff.currency,
            amount=amount,
            method=method,
            input_digest=digest,
            note=note,
        )
        self.repo.db.execute(
            "INSERT INTO finance_ledger(sequence,id,verification_id,status,body) "
            "VALUES (?,?,?,?,?)",
            (seq, str(entry.id), str(case.id), status, entry.model_dump_json()),
        )

    def _evaluate(
        self, case: Verification, command: DispatchCommand, prediction: Prediction, now: datetime
    ) -> None:
        assert command.execution_started_at and command.execution_ends_at
        end = command.execution_ends_at
        post_end = end + (end - command.execution_started_at)
        assets = prediction.evidence.asset_ids
        mapping = prediction.evidence.mapping_revisions
        execution, actual = measure(
            self.repo, command.execution_started_at, end, assets, mapping, case.baseline_kw, now
        )
        rebound, post = measure(self.repo, end, post_end, assets, mapping, case.baseline_kw, now)
        case.execution, case.rebound = execution, rebound
        case.evaluated_at = now
        if execution.quality != "COMPLETE" or rebound.quality != "COMPLETE":
            case.status = "INCOMPLETE"
            case.reason = "Missing, duplicate, bad, mismapped or late telemetry; no verified value"
        else:
            gross = Decimal(0)
            rebound_cost = Decimal(0)
            for second, kw in actual:
                rate = rate_at(case.tariff, second)
                if rate is None:
                    break
                gross += (case.baseline_kw - kw) * rate / Decimal(3600)
            else:
                for second, kw in post:
                    rate = rate_at(case.tariff, second)
                    if rate is None:
                        break
                    rebound_cost += max(Decimal(0), kw - case.baseline_kw) * rate / Decimal(3600)
                else:
                    assert (
                        execution.actual_energy_kwh is not None
                        and execution.baseline_energy_kwh is not None
                    )
                    case.status = "VERIFIED"
                    case.measured_reduction_kw = (
                        (execution.baseline_energy_kwh - execution.actual_energy_kwh)
                        * Decimal(3600)
                        / Decimal(execution.expected_slots)
                    )
                    case.rebound_kwh = sum(
                        (max(Decimal(0), kw - case.baseline_kw) for _, kw in post), Decimal(0)
                    ) / Decimal(3600)
                    case.net_energy_kwh = (
                        execution.baseline_energy_kwh
                        - execution.actual_energy_kwh
                        - case.rebound_kwh
                    )
                    case.gross_avoided_cost = gross.quantize(CENT, rounding=ROUND_HALF_UP)
                    case.rebound_cost = rebound_cost.quantize(CENT, rounding=ROUND_HALF_UP)
                    case.net_energy_value = (gross - rebound_cost).quantize(
                        CENT, rounding=ROUND_HALF_UP
                    )
                    case.reason = (
                        "Complete synthetic telemetry versus declared pre-dispatch baseline; "
                        "demand charge unassessed"
                    )
                    digest = hashlib.sha256(
                        (
                            execution.source_digest
                            + rebound.source_digest
                            + case.tariff.model_dump_json()
                            + prediction.model_dump_json()
                        ).encode()
                    ).hexdigest()
                    self.ledger(
                        case,
                        "VERIFIED",
                        case.net_energy_value,
                        "simulated-energy-baseline-minus-actual-v1",
                        digest,
                        "SIMULATED data-complete value; excludes demand charges, "
                        "settlement and causal proof",
                        now,
                    )
                    self.event(
                        "SavingsVerified",
                        case.id,
                        case.request.request_id,
                        "simulation-finance-worker",
                        now,
                    )
            if case.status != "VERIFIED":
                case.status = "INCOMPLETE"
                case.reason = "Tariff rate does not cover every execution/rebound second"
        self.repo.db.execute(
            "UPDATE finance_verifications SET status=?,body=? WHERE id=?",
            (case.status, case.model_dump_json(), str(case.id)),
        )
        self.event(
            "VerificationCompleted" if case.status == "VERIFIED" else "VerificationIncomplete",
            case.id,
            case.request.request_id,
            "simulation-finance-worker",
            now,
        )

    def tick(self, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        try:
            with self.repo.lock, self.repo.db:
                rows = self.repo.db.execute(
                    "SELECT body FROM finance_verifications WHERE status='PENDING' LIMIT 20"
                ).fetchall()
                for row in rows:
                    case = Verification.model_validate_json(row[0])
                    command = DispatchCommand.model_validate_json(
                        self.repo.db.execute(
                            "SELECT body FROM dispatch_commands WHERE id=?", (str(case.command_id),)
                        ).fetchone()[0]
                    )
                    assert command.execution_started_at and command.execution_ends_at
                    due = (
                        command.execution_ends_at
                        + (command.execution_ends_at - command.execution_started_at)
                        + timedelta(seconds=5)
                    )
                    if now < due:
                        continue
                    prediction = Prediction.model_validate_json(
                        self.repo.db.execute(
                            "SELECT body FROM predictions WHERE id=?", (str(case.prediction_id),)
                        ).fetchone()[0]
                    )
                    self._evaluate(case, command, prediction, now)
            self.worker_error = None
        except Exception:
            self.worker_error = "FINANCE_WORKER_OR_STORAGE_FAILED"

    def events(self, after: int = 0) -> list[FinanceEvent]:
        with self.repo.lock:
            return [
                FinanceEvent.model_validate_json(r[0])
                for r in self.repo.db.execute(
                    "SELECT body FROM finance_outbox WHERE sequence>? ORDER BY sequence LIMIT 100",
                    (after,),
                )
            ]

    def snapshot(self, principal: Principal, now: datetime | None = None) -> FinanceSnapshot:
        now = now or datetime.now(UTC)
        self.require(principal, "finance.read", now)
        with self.repo.lock:
            facility = self.repo.registry.records()
            timezone = next(r.entity.timezone for r in facility if r.entity.kind == "facility")
            return FinanceSnapshot(
                observed_at=now,
                timezone=timezone,
                tariffs=[
                    TariffVersion.model_validate_json(r[0])
                    for r in self.repo.db.execute(
                        "SELECT body FROM finance_tariffs ORDER BY rowid DESC LIMIT 100"
                    )
                ],
                verifications=[
                    Verification.model_validate_json(r[0])
                    for r in self.repo.db.execute(
                        "SELECT body FROM finance_verifications ORDER BY rowid DESC LIMIT 20"
                    )
                ],
                ledger=[
                    LedgerEntry.model_validate_json(r[0])
                    for r in self.repo.db.execute(
                        "SELECT body FROM finance_ledger ORDER BY sequence DESC LIMIT 100"
                    )
                ],
                pending_events=self.repo.db.execute(
                    "SELECT COUNT(*) FROM finance_outbox WHERE acknowledged=0"
                ).fetchone()[0],
                tariff_count=self.repo.db.execute(
                    "SELECT COUNT(*) FROM finance_tariffs"
                ).fetchone()[0],
                verification_count=self.repo.db.execute(
                    "SELECT COUNT(*) FROM finance_verifications"
                ).fetchone()[0],
                worker_error=self.worker_error,
            )
