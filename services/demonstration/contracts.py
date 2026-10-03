from datetime import datetime
from typing import Literal
from uuid import UUID

from edge.runtime.contracts import Contract
from services.ai.contracts import CopilotAnswer
from services.dispatch.contracts import DispatchCommand
from services.finance.contracts import Verification
from services.optimization.contracts import OptimizationRun
from services.sync.contracts import SyncSnapshot

Action = Literal[
    "normal", "bad", "peak", "propose", "approve", "verify", "explain", "disconnect", "reconnect"
]


class DemoStep(Contract):
    request_id: UUID
    action: Action


class DemoEvidence(Contract):
    action: Action
    simulated_at: datetime
    detail: str


class DemoSnapshot(Contract):
    mode: Literal["SIMULATION"] = "SIMULATION"
    clock: Literal["ACCELERATED_ISOLATED"] = "ACCELERATED_ISOLATED"
    ephemeral: Literal[True] = True
    edge_id: UUID
    org_id: UUID
    facility_id: UUID
    simulated_at: datetime
    next_action: Action | None
    steps: list[DemoEvidence]
    telemetry_rows: int
    demand_kw: float
    forecast_status: str
    risk: str
    run: OptimizationRun | None
    command: DispatchCommand | None
    verification: Verification | None
    explanation: CopilotAnswer | None
    sync: SyncSnapshot
    audit_integrity_ok: bool
    audit_head: str
