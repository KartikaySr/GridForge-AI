"""Canonical rehearsal through public domain services; no fixture SQL or history rewriting."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import RLock
from uuid import UUID, uuid4

from edge.connectors.simulator import SimulatorAdapter
from edge.storage.repository import Rejected, Repository
from services.ai.contracts import AskRequest, CopilotAnswer, DocumentWrite
from services.ai.providers import LocalEvidenceProvider
from services.ai.service import AIService
from services.demonstration.contracts import Action, DemoEvidence, DemoSnapshot, DemoStep
from services.dispatch.contracts import ApprovalRequest, DecisionRequest, DispatchCommand
from services.dispatch.permissions import Principal
from services.dispatch.service import DispatchService
from services.finance.contracts import (
    EnergyBand,
    TariffInput,
    TariffWrite,
    Verification,
    VerificationRequest,
)
from services.finance.service import FinanceService
from services.forecasting.service import ForecastService
from services.optimization.contracts import OptimizationRun, PolicyInput, PolicyWrite, RunRequest
from services.optimization.service import OptimizationService
from services.registry.contracts import Asset, Facility, RegistryWrite
from services.security.audit import AuditService
from services.sync.contracts import CloudSyncState, SyncAck, SyncBatch
from services.sync.service import CloudTransport, SyncFailure, SyncService

ACTIONS: list[Action] = [
    "normal",
    "bad",
    "peak",
    "propose",
    "approve",
    "verify",
    "explain",
    "disconnect",
    "reconnect",
]


class NetworkGate:
    """Fault injection around a real transport; never fabricates acknowledgements."""

    def __init__(self, transport: CloudTransport) -> None:
        self.transport = transport
        self.offline = False

    def state(self, edge_id: UUID, token: str) -> CloudSyncState:
        if self.offline:
            raise SyncFailure("CLOUD_UNAVAILABLE")
        return self.transport.state(edge_id, token)

    def upload(self, batch: SyncBatch, token: str) -> SyncAck:
        if self.offline:
            raise SyncFailure("CLOUD_UNAVAILABLE")
        return self.transport.upload(batch, token)


class DemoService:
    def __init__(self) -> None:
        self.repo = Repository(None)
        self.lock = RLock()
        self.now = datetime.now(UTC).replace(second=0, microsecond=0) - timedelta(minutes=30)
        self.origin = self.now
        self.adapter = SimulatorAdapter(self.repo.registry)
        self.forecasting = ForecastService(self.repo)
        self.optimization = OptimizationService(self.repo, self.forecasting)
        self.dispatch = DispatchService(self.repo, self.forecasting)
        self.finance = FinanceService(self.repo)
        self.audit = AuditService(self.repo)
        self.ai = AIService(self.repo, LocalEvidenceProvider())
        # Rehearsal evidence must stay isolated even if the main runtime has central AI configured.
        self.ai.central_knowledge = None
        self.ai.query_dsn = None
        self.sync = SyncService(self.repo)
        self.network: NetworkGate | None = None
        self.steps: list[DemoEvidence] = []
        self.receipts: dict[UUID, tuple[Action, DemoSnapshot]] = {}
        self.run: OptimizationRun | None = None
        self.command: DispatchCommand | None = None
        self.verification: Verification | None = None
        self.explanation: CopilotAnswer | None = None
        self.tick = 0
        self.scenario = "normal"
        self.configured = False

    def close(self) -> None:
        self.repo.close()

    def connect(self, transport: CloudTransport, token: str) -> None:
        self.network = NetworkGate(transport)
        self.sync = SyncService(self.repo, token=token, transport=self.network)

    def actor(self, principal: Principal) -> Principal:
        # Called only after the host has checked the caller's facility scope and permissions.
        return replace(principal, org_id=self.repo.org_id, facility_id=self.repo.facility_id)

    def configure(self) -> None:
        threshold = (
            sum(
                r.entity.rated_kw
                for r in self.repo.registry.records()
                if isinstance(r.entity, Asset)
            )
            * 1.2
        )
        for record in self.repo.registry.records():
            entity = record.entity
            if isinstance(entity, Facility):
                entity = entity.model_copy(update={"simulation_demand_threshold_kw": threshold})
            elif isinstance(entity, Asset):
                changes = (
                    {"criticality": "CRITICAL"}
                    if entity.id == "SIM-5"
                    else {
                        "flexible": True,
                        "capabilities": ["telemetry", "simulated_load_adjustment"],
                        "max_reduction_kw": entity.rated_kw * 0.6,
                    }
                )
                entity = Asset.model_validate(entity.model_dump() | changes)
            else:
                continue
            self.repo.registry.save(
                RegistryWrite(request_id=uuid4(), expected_revision=record.revision, entity=entity)
            )
        self.configured = True

    def advance(self, seconds: int) -> None:
        for _ in range(seconds):
            self.now += timedelta(seconds=1)
            self.tick += 1
            batch = self.adapter.poll(self.tick, self.now, self.scenario)
            if batch is None:
                raise Rejected("DEMO_NO_TELEMETRY")
            self.repo.ingest(batch, self.now, self.tick)
            self.dispatch.tick(now=self.now + timedelta(milliseconds=100))
        self.forecasting.run(self.now + timedelta(milliseconds=200))

    def drain(self, actor: Principal) -> None:
        for attempt in range(500):
            self.sync.tick(self.now + timedelta(seconds=attempt + 10))
            if self.sync.snapshot(actor, self.now).pending_count == 0:
                return
            if self.sync.state in {"CONFLICT", "OFFLINE", "NOT_CONFIGURED"}:
                raise Rejected("DEMO_CLOUD_RECONCILIATION_FAILED")
        raise Rejected("DEMO_CLOUD_BACKLOG_LIMIT")

    def step(self, write: DemoStep, principal: Principal) -> DemoSnapshot:
        actor = self.actor(principal)
        actor.require(
            "system.configure", self.repo.org_id, self.repo.facility_id, datetime.now(UTC)
        )
        with self.lock:
            saved = self.receipts.get(write.request_id)
            if saved:
                if saved[0] != write.action:
                    raise Rejected("IDEMPOTENCY_CONFLICT")
                return saved[1]
            if len(self.steps) >= len(ACTIONS) or write.action != ACTIONS[len(self.steps)]:
                raise Rejected("DEMO_STEP_OUT_OF_ORDER")
            detail = self.execute(write.action, actor)
            self.audit.record("demo." + write.action, "success", actor.actor, write.request_id)
            self.steps.append(
                DemoEvidence(action=write.action, simulated_at=self.now, detail=detail)
            )
            result = self.snapshot(principal)
            self.receipts[write.request_id] = (write.action, result)
            return result

    def execute(self, action: Action, actor: Principal) -> str:
        if action == "normal":
            if not self.configured:
                self.configure()
            self.advance(301)
            if self.forecasting.snapshot(now=self.now).risk_assessment != "CLEAR":
                raise Rejected("DEMO_NORMAL_NOT_CLEAR")
            return (
                "301 seconds of real simulator samples ingested; normal demand is "
                "below the declared synthetic threshold."
            )
        if action == "bad":
            self.scenario = "bad"
            self.advance(1)
            if self.forecasting.snapshot(now=self.now).risk_assessment != "UNKNOWN":
                raise Rejected("DEMO_QUALITY_GATE_FAILED")
            return "Bad-quality samples suppress prediction and produce UNKNOWN risk."
        if action == "peak":
            self.scenario = "spike"
            self.advance(360)
            if self.forecasting.snapshot(now=self.now).risk_assessment != "BREACH":
                raise Rejected("DEMO_PEAK_NOT_DETECTED")
            return (
                "Six simulated minutes of elevated demand restore coverage and "
                "create a forecast threshold breach."
            )
        if action == "propose":
            policy = self.optimization.save_policy(
                PolicyWrite(
                    request_id=uuid4(),
                    policy=PolicyInput(
                        name="Isolated demonstration policy",
                        effective_from=self.now - timedelta(minutes=1),
                        effective_until=self.now + timedelta(hours=1),
                        max_duration_seconds=300,
                        max_total_reduction_kw=2000,
                        simulation_rate_per_kwh=Decimal("0.15"),
                    ),
                ),
                self.now,
            )
            self.run = self.optimization.run(
                RunRequest(request_id=uuid4(), policy_id=policy.id, duration_seconds=60),
                now=self.now,
            )
            if not self.run.proposal:
                raise Rejected("DEMO_NO_PROPOSAL")
            self.command = self.dispatch.request(
                ApprovalRequest(request_id=uuid4(), run_id=self.run.id), actor, now=self.now
            )
            return (
                "Constraint evidence retained; critical asset excluded. Command "
                "awaits a separate explicit human approval."
            )
        if action == "approve":
            actor.require(
                "dispatch.approve", self.repo.org_id, self.repo.facility_id, datetime.now(UTC)
            )
            if self.command is None:
                raise Rejected("DEMO_COMMAND_MISSING")
            self.command = self.dispatch.decide(
                DecisionRequest(
                    request_id=uuid4(),
                    command_id=self.command.id,
                    expected_revision=self.command.revision,
                    action="approve",
                    reason="Operator explicitly approved isolated simulation rehearsal",
                ),
                actor,
                now=self.now,
            )
            # Fine-grained ACK/start transitions keep the initial guard evidence fresh.
            for offset in (0.1, 1.2, 1.3):
                self.dispatch.tick(now=self.now + timedelta(seconds=offset))
            self.now += timedelta(seconds=1)
            self.advance(62)
            self.command = self.dispatch.load(self.command.id)
            if self.command.state != "COMPLETED":
                raise Rejected("DEMO_DISPATCH_NOT_COMPLETED")
            return (
                "Approved command acknowledged and executed by the durable "
                "simulator; measured synthetic load response retained."
            )
        if action == "verify":
            if self.command is None:
                raise Rejected("DEMO_COMMAND_MISSING")
            end = self.origin + timedelta(hours=2)
            tariff = self.finance.tariff(
                TariffWrite(
                    request_id=uuid4(),
                    tariff=TariffInput(
                        name="Declared demonstration tariff",
                        currency="USD",
                        effective_from=self.origin,
                        effective_until=end,
                        billing_period_start=self.origin,
                        billing_period_end=end,
                        energy_bands=[
                            EnergyBand(
                                starts_at=self.origin, ends_at=end, rate_per_kwh=Decimal("0.15")
                            )
                        ],
                    ),
                ),
                actor,
                self.now,
            )
            started = self.finance.start(
                VerificationRequest(
                    request_id=uuid4(), command_id=self.command.id, tariff_id=tariff.id
                ),
                actor,
                self.now,
            )
            self.advance(65)
            self.finance.tick(self.now)
            self.verification = next(
                v
                for v in self.finance.snapshot(actor, self.now).verifications
                if v.id == started.id
            )
            if self.verification.status != "VERIFIED":
                raise Rejected("DEMO_VERIFICATION_INCOMPLETE")
            return (
                f"Execution and rebound measured without history edits. Verified "
                f"SIMULATED net value: {self.verification.net_energy_value} USD."
            )
        if action == "explain":
            if self.run is None or self.command is None or self.verification is None:
                raise Rejected("DEMO_EVIDENCE_MISSING")
            evidence = (
                f"Demonstration savings explanation. Forecast {self.run.prediction_id} "
                f"exceeded {self.run.threshold_kw} kW. Proposal {self.command.proposal_id} "
                "used only eligible flexible assets. "
                f"Operator {self.command.approved_by} approved command {self.command.id}. "
                f"Verification {self.verification.id} measured execution and rebound. "
                f"Net value {self.verification.net_energy_value} USD is SIMULATION only. "
                "Critical equipment was excluded; no physical actuation occurred."
            )
            self.ai.ingest(
                DocumentWrite(
                    request_id=uuid4(),
                    document_key="demo-evidence",
                    revision=1,
                    title="Demonstration decision evidence",
                    source="Local domain records",
                    text=evidence,
                ),
                actor,
            )
            self.explanation = self.ai.ask(
                AskRequest(
                    request_id=uuid4(),
                    question="Explain demonstration savings and operator approval.",
                ),
                actor,
            )
            if self.explanation.status != "ANSWERED" or not self.explanation.evidence:
                raise Rejected("DEMO_EXPLANATION_MISSING")
            return (
                "Advisory extractive explanation cites generated domain evidence "
                "and cannot dispatch."
            )
        if self.network is None:
            raise Rejected("DEMO_CLOUD_NOT_CONFIGURED")
        if action == "disconnect":
            self.drain(actor)
            self.network.offline = True
            self.advance(10)
            self.sync.tick(self.now + timedelta(hours=1))
            if self.sync.snapshot(actor, self.now).pending_count < 50:
                raise Rejected("DEMO_CONTINUITY_FAILED")
            return (
                "Real cloud transport disconnected; 50 further telemetry points "
                "persisted locally with pending sync."
            )
        self.network.offline = False
        self.sync.next_attempt_at = None
        self.drain(actor)
        return (
            "Real receiver acknowledged the backlog; reconciliation completed "
            "without duplicate inserts."
        )

    def snapshot(self, principal: Principal) -> DemoSnapshot:
        with self.lock:
            actor = self.actor(principal)
            info = self.forecasting.snapshot(now=self.now)
            audit = self.audit.snapshot()
            return DemoSnapshot(
                edge_id=self.repo.edge_id,
                org_id=self.repo.org_id,
                facility_id=self.repo.facility_id,
                simulated_at=self.now,
                next_action=ACTIONS[len(self.steps)] if len(self.steps) < len(ACTIONS) else None,
                steps=self.steps,
                telemetry_rows=self.repo.state()[2]["accepted"],
                demand_kw=sum(p.value for p in self.repo.state()[1]),
                forecast_status=info.status,
                risk=info.risk_assessment,
                run=self.run,
                command=self.command,
                verification=self.verification,
                explanation=self.explanation,
                sync=self.sync.snapshot(actor, self.now),
                audit_integrity_ok=audit.integrity_ok,
                audit_head=audit.head,
            )
