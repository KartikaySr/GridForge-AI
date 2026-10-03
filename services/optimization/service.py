import hashlib
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from edge.storage.repository import CapacityError, Rejected
from services.forecasting.service import ForecastService
from services.optimization.contracts import (
    EconomicEstimate,
    OptimizationEvent,
    OptimizationPolicy,
    OptimizationRun,
    OptimizationSnapshot,
    PolicyWrite,
    Proposal,
    RunRequest,
)
from services.optimization.engine import allocate, evaluate, gate
from services.registry.contracts import Asset

if TYPE_CHECKING:
    from edge.storage.repository import Repository


class OptimizationService:
    capacity = 500

    def __init__(self, repo: "Repository", forecasting: ForecastService) -> None:
        self.repo = repo
        self.forecasting = forecasting

    def emit(self, kind: str, resource: UUID, correlation: UUID, now: datetime) -> None:
        seq = self.repo.db.execute(
            "SELECT COALESCE(MAX(sequence),0)+1 FROM optimization_outbox"
        ).fetchone()[0]
        event = OptimizationEvent.model_validate(
            dict(
                sequence=seq,
                event_id=uuid4(),
                event_type=kind,
                occurred_at=now,
                org_id=self.repo.org_id,
                facility_id=self.repo.facility_id,
                correlation_id=correlation,
                causation_id=correlation,
                idempotency_key=uuid4(),
                resource_id=resource,
            )
        )
        self.repo.db.execute(
            "INSERT INTO optimization_outbox(sequence,event_id,body) VALUES (?,?,?)",
            (seq, str(event.event_id), event.model_dump_json()),
        )

    def save_policy(self, write: PolicyWrite, now: datetime | None = None) -> OptimizationPolicy:
        now = now or datetime.now(UTC)
        fingerprint = hashlib.sha256(write.model_dump_json().encode()).hexdigest()
        with self.repo.lock, self.repo.db:
            row = self.repo.db.execute(
                "SELECT fingerprint,body FROM optimization_policies WHERE request_id=?",
                (str(write.request_id),),
            ).fetchone()
            if row:
                if row[0] != fingerprint:
                    raise Rejected("IDEMPOTENCY_CONFLICT")
                return OptimizationPolicy.model_validate_json(row[1])
            if (
                self.repo.db.execute("SELECT COUNT(*) FROM optimization_policies").fetchone()[0]
                >= 100
            ):
                raise CapacityError("POLICY_CAPACITY")
            assets = {
                r.entity.id for r in self.repo.registry.records() if isinstance(r.entity, Asset)
            }
            if not set(write.policy.asset_penalties) <= assets:
                raise Rejected("UNKNOWN_POLICY_ASSET")
            policy = OptimizationPolicy(
                **write.policy.model_dump(),
                id=uuid4(),
                org_id=self.repo.org_id,
                facility_id=self.repo.facility_id,
                created_at=now,
            )
            self.repo.db.execute(
                "INSERT INTO optimization_policies VALUES (?,?,?,?)",
                (str(policy.id), str(write.request_id), fingerprint, policy.model_dump_json()),
            )
            self.emit("OptimizationPolicyCreated", policy.id, write.request_id, now)
            return policy

    def run(
        self, request: RunRequest, disconnected: bool = False, now: datetime | None = None
    ) -> OptimizationRun:
        now = now or datetime.now(UTC)
        fingerprint = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        # Lock ingestion/configuration through evaluation and transactional persistence.
        with self.repo.lock, self.repo.db:
            row = self.repo.db.execute(
                "SELECT fingerprint,body FROM optimization_runs WHERE request_id=?",
                (str(request.request_id),),
            ).fetchone()
            if row:
                if row[0] != fingerprint:
                    raise Rejected("IDEMPOTENCY_CONFLICT")
                return OptimizationRun.model_validate_json(row[1])
            if (
                self.repo.db.execute("SELECT COUNT(*) FROM optimization_runs").fetchone()[0]
                >= self.capacity
            ):
                raise CapacityError("OPTIMIZATION_CAPACITY")
            row = self.repo.db.execute(
                "SELECT body FROM optimization_policies WHERE id=?", (str(request.policy_id),)
            ).fetchone()
            if not row:
                raise Rejected("POLICY_NOT_FOUND")
            policy = OptimizationPolicy.model_validate_json(row[0])
            intelligence = self.forecasting.snapshot(disconnected, now)
            prediction = intelligence.latest
            facility, _, _, _, digest = self.forecasting.context()
            records = self.repo.registry.records()
            points = self.repo.state()[1]
            by_asset = {p.asset_id: p for p in points}
            end = now + timedelta(seconds=request.duration_seconds)
            peak = (
                max(p.value_kw for p in prediction.values)
                if prediction and prediction.values
                else None
            )
            threshold = intelligence.threshold_kw
            target = (
                max(0, peak - threshold) if peak is not None and threshold is not None else None
            )
            checks = [
                gate(
                    "INPUT_READY",
                    intelligence.status == "READY",
                    intelligence.reason or "Current forecast and telemetry are ready",
                ),
                gate(
                    "FACILITY_ENABLED",
                    facility.enabled
                    and all(r.entity.enabled for r in records if r.entity.kind == "organization"),
                    "Facility and organization enabled",
                ),
                gate(
                    "THRESHOLD_CONFIGURED",
                    threshold is not None,
                    "User-configured simulation demand threshold required",
                ),
                gate(
                    "POLICY_WINDOW",
                    policy.effective_from <= now and end <= policy.effective_until,
                    "Entire action must fit immutable policy window",
                ),
                gate(
                    "DURATION_BOUND",
                    request.duration_seconds <= policy.max_duration_seconds,
                    "Action duration must respect policy bound",
                ),
                gate(
                    "FORECAST_HORIZON",
                    bool(prediction and prediction.values and end <= prediction.values[-1].ends_at),
                    "Action must fit available forecast horizon",
                ),
            ]
            candidates = [
                evaluate(r.entity, records, by_asset.get(r.entity.id), policy, now, end)
                for r in records
                if isinstance(r.entity, Asset)
            ]
            passed = all(c.passed for c in checks)
            feasible = (
                passed
                and target is not None
                and allocate(candidates, target, policy.max_total_reduction_kw)
            )
            checks.append(
                gate(
                    "SUFFICIENT_FLEXIBILITY",
                    feasible,
                    "Eligible bounded reductions must fully cover forecast excess and "
                    "remain inside policy total cap",
                )
            )
            status = (
                "PROPOSED" if feasible and target else "NO_ACTION" if feasible else "INFEASIBLE"
            )
            explanation = (
                "All hard gates pass; lowest relative penalty reductions cover the forecast excess."
                if status == "PROPOSED"
                else "Forecast does not exceed the configured threshold; no action selected."
                if status == "NO_ACTION"
                else "No proposal: " + ", ".join(c.code for c in checks if not c.passed)
            )
            proposal = None
            if status == "PROPOSED":
                assert target is not None and prediction is not None
                energy = Decimal(str(target)) * Decimal(request.duration_seconds) / Decimal(3600)
                rate = policy.simulation_rate_per_kwh
                estimate = EconomicEstimate(
                    status="INCOMPLETE" if rate is None else "ESTIMATED",
                    amount=None
                    if rate is None
                    else (energy * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    currency=policy.currency,
                    simulation_rate_per_kwh=rate,
                    energy_kwh=energy.quantize(Decimal("0.000001")),
                )
                proposal = Proposal(
                    id=uuid4(),
                    expected_reduction_kw=target,
                    expires_at=min(
                        prediction.expires_at, now + timedelta(seconds=5), policy.effective_until
                    ),
                    economic_estimate=estimate,
                    explanation=explanation
                    + " Constant curtailment is hypothetical; authorization and fresh "
                    "constraint validation are required before any later simulated dispatch.",
                )
            seq = self.repo.db.execute(
                "SELECT COALESCE(MAX(sequence),0)+1 FROM optimization_runs"
            ).fetchone()[0]
            run = OptimizationRun.model_validate(
                dict(
                    sequence=seq,
                    id=uuid4(),
                    org_id=self.repo.org_id,
                    facility_id=self.repo.facility_id,
                    created_at=now,
                    ends_at=end,
                    status=status,
                    request=request,
                    policy=policy,
                    prediction_id=prediction.id if prediction else None,
                    risk_ids=[r.id for r in intelligence.risks if r.state == "OPEN"],
                    registry_digest=digest,
                    registry=records,
                    telemetry=points,
                    forecast_peak_kw=peak,
                    threshold_kw=threshold,
                    required_reduction_kw=target,
                    constraints=checks,
                    candidates=candidates,
                    proposal=proposal,
                    explanation=explanation,
                )
            )
            self.repo.db.execute(
                "INSERT INTO optimization_runs VALUES (?,?,?,?,?,?)",
                (
                    seq,
                    str(run.id),
                    str(request.request_id),
                    fingerprint,
                    str(policy.id),
                    run.model_dump_json(),
                ),
            )
            self.emit("OptimizationStarted", run.id, request.request_id, now)
            self.emit(
                {
                    "PROPOSED": "ProposalCreated",
                    "INFEASIBLE": "OptimizationInfeasible",
                    "NO_ACTION": "OptimizationNoAction",
                }[status],
                proposal.id if proposal else run.id,
                request.request_id,
                now,
            )
            return run

    def history(self, before: int | None = None) -> list[OptimizationRun]:
        with self.repo.lock:
            return [
                OptimizationRun.model_validate_json(r[0])
                for r in self.repo.db.execute(
                    "SELECT body FROM optimization_runs WHERE sequence < ? ORDER BY "
                    "sequence DESC LIMIT 1",
                    (before or 9223372036854775807,),
                )
            ]

    def events(self, after: int = 0) -> list[OptimizationEvent]:
        with self.repo.lock:
            return [
                OptimizationEvent.model_validate_json(r[0])
                for r in self.repo.db.execute(
                    "SELECT body FROM optimization_outbox WHERE sequence>? ORDER BY "
                    "sequence LIMIT 100",
                    (after,),
                )
            ]

    def snapshot(
        self, disconnected: bool = False, now: datetime | None = None
    ) -> OptimizationSnapshot:
        now = now or datetime.now(UTC)
        with self.repo.lock:
            runs = self.history()
            latest = runs[0] if runs else None
            facility, _, _, _, digest = self.forecasting.context()
            current = bool(
                latest
                and latest.proposal
                and now <= latest.proposal.expires_at
                and now >= latest.created_at
                and latest.registry_digest == digest
                and not self.forecasting.live_reason(now, disconnected)
            )
            return OptimizationSnapshot(
                observed_at=now,
                timezone=facility.timezone,
                policies=[
                    OptimizationPolicy.model_validate_json(r[0])
                    for r in self.repo.db.execute(
                        "SELECT body FROM optimization_policies ORDER BY rowid DESC LIMIT 100"
                    )
                ],
                latest=latest,
                latest_is_current=current,
                pending_events=self.repo.db.execute(
                    "SELECT COUNT(*) FROM optimization_outbox WHERE acknowledged=0"
                ).fetchone()[0],
                run_count=self.repo.db.execute("SELECT COUNT(*) FROM optimization_runs").fetchone()[
                    0
                ],
                capacity=self.capacity,
            )
