"""Local composition root. It intentionally does not mount the legacy scaffold API."""

import asyncio
import json
import os
import secrets
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse

from edge.runtime.contracts import Diagnostics, RuntimeErrorResponse, RuntimeHealth
from edge.runtime.state import RuntimeState
from edge.runtime.telemetry import TelemetryRuntime
from edge.storage.repository import CapacityError, Rejected
from services.ai.contracts import (
    AskRequest,
    CopilotAnswer,
    CopilotSnapshot,
    DocumentWrite,
    FeedbackReceipt,
    FeedbackWrite,
    KnowledgeDocument,
    QueryRun,
)
from services.ai.service import AIRejected, AIService
from services.demonstration.contracts import DemoSnapshot, DemoStep
from services.demonstration.service import DemoService
from services.dispatch.contracts import (
    ApprovalRequest,
    DecisionRequest,
    DispatchCommand,
    DispatchDetail,
    DispatchEvent,
    DispatchSnapshot,
)
from services.dispatch.permissions import SIMULATION_PERMISSIONS, PermissionDenied, Principal
from services.finance.contracts import (
    FinanceEvent,
    FinanceSnapshot,
    TariffVersion,
    TariffWrite,
    Verification,
    VerificationRequest,
)
from services.forecasting.contracts import IntelligenceEvent, IntelligenceSnapshot, Prediction
from services.operations.service import OperationsService
from services.optimization.contracts import (
    OptimizationEvent,
    OptimizationPolicy,
    OptimizationRun,
    OptimizationSnapshot,
    PolicyWrite,
    RunRequest,
)
from services.optimization.service import OptimizationService
from services.registry.contracts import (
    ConfigurationEvent,
    RegistryRecord,
    RegistrySnapshot,
    RegistryWrite,
)
from services.registry.service import RegistryError
from services.security.audit import AuditService
from services.security.contracts import (
    AuditSnapshot,
    IdentityStatus,
    LocalUser,
    Login,
    OperationsSnapshot,
    UserChange,
    UserWrite,
)
from services.security.identity import IdentityRejected, IdentityService
from services.security.policy import route_permission
from services.sync.contracts import SyncSnapshot
from services.sync.service import HttpCloudTransport
from services.telemetry.contracts import (
    HistoryPage,
    IngestResult,
    ScenarioRequest,
    TelemetryBatch,
    TelemetryEvent,
    TelemetrySnapshot,
)

request_principal: ContextVar[Principal] = ContextVar("request_principal")


def create_app(
    token: str,
    instance_id: UUID,
    db_path: Path | None = None,
    *,
    simulate: bool = True,
    principal: Principal | None = None,
    identity_required: bool = True,
) -> FastAPI:
    if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
        raise ValueError("A 256-bit session credential is required")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        telemetry = TelemetryRuntime(db_path, simulate)
        app.state.telemetry = telemetry
        app.state.optimization = OptimizationService(telemetry.repo, telemetry.forecasting)
        app.state.ai = AIService(telemetry.repo)
        app.state.audit = AuditService(telemetry.repo)
        app.state.identity = IdentityService(telemetry.repo, app.state.audit, instance_id)
        app.state.operations = OperationsService(telemetry.repo, app.state.audit)
        app.state.demo = DemoService()
        demo_url = os.environ.get("GRIDFORGE_DEMO_CLOUD_URL")
        demo_token = os.environ.get("GRIDFORGE_DEMO_EDGE_TOKEN")
        if demo_url and demo_token:
            app.state.demo.connect(HttpCloudTransport(demo_url), demo_token)
        state.telemetry = telemetry
        app.state.trusted_principal = principal or Principal(
            actor=f"local-simulation-edge:{telemetry.repo.edge_id}",
            org_id=telemetry.repo.org_id,
            facility_id=telemetry.repo.facility_id,
            permissions=SIMULATION_PERMISSIONS,
            expires_at=datetime.now(UTC) + timedelta(hours=8),
        )
        await telemetry.start()
        try:
            yield
        finally:
            app.state.demo.close()
            await telemetry.close()

    app = FastAPI(
        lifespan=lifespan,
        title="GridForge Edge Runtime",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    state = RuntimeState(instance_id)

    @app.middleware("http")
    async def authenticate(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = uuid4()
        started = time.monotonic()
        # No browser origin is trusted: the native host makes authenticated requests.
        # No user-supplied path/query/header/body is ever copied into diagnostic logs.
        supplied = request.headers.get("authorization", "")
        if request.headers.get("origin") or not secrets.compare_digest(
            supplied.encode(), f"Bearer {token}".encode()
        ):
            state.record("request.denied", request_id=request_id, outcome="denied")
            error = RuntimeErrorResponse(
                code="LOCAL_AUTH_REQUIRED",
                message="Authenticated native session required",
                details={},
                request_id=request_id,
            )
            return JSONResponse(
                status_code=401,
                content=error.model_dump(mode="json"),
                headers={"X-Request-ID": str(request_id), "Cache-Control": "no-store"},
            )
        request.state.request_id = request_id
        if request.method == "POST":
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 65536:
                    app.state.telemetry.repo.count("rejected")
                    return failure(request, "PAYLOAD_TOO_LARGE", 413)
            request._body = bytes(body)
        identity: IdentityService = app.state.identity
        audit: AuditService = app.state.audit
        actor = principal or (
            identity.current() if identity_required else app.state.trusted_principal
        )
        correlation_id = request_id
        kind = None
        if request.method == "POST":
            try:
                parsed = json.loads(await request.body())
                if isinstance(parsed, dict):
                    if parsed.get("request_id"):
                        correlation_id = UUID(str(parsed["request_id"]))
                    entity = parsed.get("entity")
                    kind = entity.get("kind") if isinstance(entity, dict) else None
            except (ValueError, TypeError):
                pass
        permission = route_permission(request.method, request.url.path, kind)
        route_label = permission or "native.session"
        if permission:
            try:
                if actor is None:
                    raise PermissionDenied("USER_LOGIN_REQUIRED")
                actor.require(
                    permission,
                    app.state.telemetry.repo.org_id,
                    app.state.telemetry.repo.facility_id,
                    datetime.now(UTC),
                )
            except PermissionDenied as exc:
                try:
                    audit.record(
                        route_label,
                        "denied",
                        actor.actor if actor else "anonymous",
                        request_id,
                        correlation_id,
                    )
                except Exception:
                    pass
                app.state.operations.request(
                    route_label, 403, round((time.monotonic() - started) * 1000, 3)
                )
                return failure(request, str(exc), 403)
        audited_mutation = (
            request.method == "POST" and request.url.path != "/api/v1/identity/logout"
        )
        if audited_mutation and not audit.integrity_ok:
            return failure(request, "AUDIT_INTEGRITY_FAILURE", 503)
        if actor is not None:
            context_token = request_principal.set(actor)
        if audited_mutation:
            try:
                audit.record(
                    route_label,
                    "started",
                    actor.actor if actor else "anonymous",
                    request_id,
                    correlation_id,
                )
            except Exception:
                return failure(request, "AUDIT_UNAVAILABLE", 503)
        try:
            response = await call_next(request)
        except Exception:
            state.record("request.failed", request_id=request_id, outcome="failure")
            error = RuntimeErrorResponse(
                code="RUNTIME_ERROR",
                message="Local runtime request failed",
                details={},
                request_id=request_id,
            )
            response = JSONResponse(status_code=500, content=error.model_dump(mode="json"))
        if response.status_code == 404:
            response = JSONResponse(
                status_code=404,
                content=RuntimeErrorResponse(
                    code="NOT_FOUND",
                    message="Runtime route not available",
                    details={},
                    request_id=request_id,
                ).model_dump(mode="json"),
            )
        app.state.operations.request(
            route_label, response.status_code, round((time.monotonic() - started) * 1000, 3)
        )
        if actor is not None:
            request_principal.reset(context_token)
        if audited_mutation:
            try:
                audit.record(
                    route_label,
                    "success" if response.status_code < 400 else "failure",
                    actor.actor if actor else "anonymous",
                    request_id,
                    correlation_id,
                )
            except Exception:
                audit.integrity_ok = False
                response = failure(request, "AUDIT_COMPLETION_UNAVAILABLE", 503)
        response.headers["X-Request-ID"] = str(request_id)
        response.headers["X-Trace-ID"] = str(correlation_id)
        response.headers["Cache-Control"] = "no-store"
        state.record(
            "request.completed",
            request_id=request_id,
            outcome="success" if response.status_code < 400 else "failure",
            duration_ms=round((time.monotonic() - started) * 1000, 3),
        )
        return response

    errors: dict[int | str, dict[str, Any]] = {
        401: {"model": RuntimeErrorResponse},
        403: {"model": RuntimeErrorResponse},
        409: {"model": RuntimeErrorResponse},
        413: {"model": RuntimeErrorResponse},
        422: {"model": RuntimeErrorResponse},
        429: {"model": RuntimeErrorResponse},
        500: {"model": RuntimeErrorResponse},
    }

    @app.get("/api/v1/system/health", response_model=RuntimeHealth, responses=errors)
    def health() -> RuntimeHealth:
        return state.health()

    @app.get("/api/v1/system/diagnostics", response_model=Diagnostics, responses=errors)
    def diagnostics() -> Diagnostics:
        return state.diagnostics()

    def failure(request: Request, code: str, status: int) -> JSONResponse:
        return JSONResponse(
            status_code=status,
            content=RuntimeErrorResponse(
                code=code,
                message="Local request rejected",
                details={},
                request_id=request.state.request_id,
            ).model_dump(mode="json"),
            headers={"Cache-Control": "no-store", "X-Request-ID": str(request.state.request_id)},
        )

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        app.state.telemetry.repo.count("rejected")
        return failure(request, "INVALID_PAYLOAD", 422)

    @app.exception_handler(IdentityRejected)
    async def identity_error(request: Request, exc: IdentityRejected) -> JSONResponse:
        return failure(request, str(exc), 409)

    @app.exception_handler(Rejected)
    async def rejected(request: Request, exc: Rejected) -> JSONResponse:
        return failure(request, str(exc), 409)

    @app.exception_handler(CapacityError)
    async def full(request: Request, exc: CapacityError) -> JSONResponse:
        return failure(request, str(exc), 429)

    @app.exception_handler(RegistryError)
    async def registry_error(request: Request, exc: RegistryError) -> JSONResponse:
        return failure(request, str(exc), 409)

    @app.exception_handler(PermissionDenied)
    async def denied(request: Request, exc: PermissionDenied) -> JSONResponse:
        state.record(
            "dispatch.permission_denied", request_id=request.state.request_id, outcome="denied"
        )
        return failure(request, str(exc), 403)

    @app.get("/api/v1/demo", response_model=DemoSnapshot, responses=errors)
    def demo_read() -> DemoSnapshot:
        service: DemoService = app.state.demo
        return service.snapshot(request_principal.get())

    @app.post("/api/v1/demo", response_model=DemoSnapshot, responses=errors)
    def demo_step(write: DemoStep) -> DemoSnapshot:
        service: DemoService = app.state.demo
        return service.step(write, request_principal.get())

    @app.get("/api/v1/identity", response_model=IdentityStatus, responses=errors)
    def identity_status() -> IdentityStatus:
        service: IdentityService = app.state.identity
        return service.status()

    @app.post("/api/v1/identity/bootstrap", response_model=IdentityStatus, responses=errors)
    def identity_bootstrap(write: Login) -> IdentityStatus:
        service: IdentityService = app.state.identity
        service.create(UserWrite(**write.model_dump(), role="ORG_ADMIN"))
        return service.login(write)

    @app.post("/api/v1/identity/login", response_model=IdentityStatus, responses=errors)
    def identity_login(write: Login) -> IdentityStatus:
        service: IdentityService = app.state.identity
        return service.login(write)

    @app.post("/api/v1/identity/logout", response_model=IdentityStatus, responses=errors)
    def identity_logout() -> IdentityStatus:
        service: IdentityService = app.state.identity
        return service.logout()

    @app.get("/api/v1/identity/users", response_model=list[LocalUser], responses=errors)
    def identity_users() -> list[LocalUser]:
        service: IdentityService = app.state.identity
        return service.users()

    @app.post("/api/v1/identity/users", response_model=LocalUser, responses=errors)
    def identity_create(write: UserWrite) -> LocalUser:
        service: IdentityService = app.state.identity
        return service.create(write, request_principal.get())

    @app.post("/api/v1/identity/users/change", response_model=LocalUser, responses=errors)
    def identity_change(write: UserChange) -> LocalUser:
        service: IdentityService = app.state.identity
        return service.change(write, request_principal.get())

    @app.get("/api/v1/security/audit", response_model=AuditSnapshot, responses=errors)
    def audit_snapshot(after: int = Query(default=0, ge=0)) -> AuditSnapshot:
        audit: AuditService = app.state.audit
        return audit.snapshot(after)

    @app.get("/api/v1/system/metrics", response_model=OperationsSnapshot, responses=errors)
    def operations_snapshot() -> OperationsSnapshot:
        service: OperationsService = app.state.operations
        return service.snapshot()

    @app.get("/api/v1/system/bundle", responses=errors)
    def diagnostic_bundle() -> dict[str, object]:
        service: OperationsService = app.state.operations
        return service.bundle(state.diagnostics())

    @app.get("/api/v1/system/authorize", responses=errors)
    def authorize_lifecycle() -> dict[str, bool]:
        return {"authorized": True}

    @app.get("/api/v1/dispatch", response_model=DispatchSnapshot, responses=errors)
    def dispatch_snapshot() -> DispatchSnapshot:
        runtime: TelemetryRuntime = app.state.telemetry
        return runtime.dispatch.snapshot(request_principal.get())

    @app.get("/api/v1/finance", response_model=FinanceSnapshot, responses=errors)
    def finance_snapshot() -> FinanceSnapshot:
        runtime: TelemetryRuntime = app.state.telemetry
        return runtime.finance.snapshot(request_principal.get())

    @app.exception_handler(AIRejected)
    async def ai_rejected(request: Request, exc: AIRejected) -> JSONResponse:
        return failure(request, str(exc), 409)

    @app.get("/api/v1/ai", response_model=CopilotSnapshot, responses=errors)
    def ai_snapshot() -> CopilotSnapshot:
        service: AIService = app.state.ai
        return service.snapshot(request_principal.get())

    @app.post("/api/v1/ai/documents", response_model=KnowledgeDocument, responses=errors)
    def ai_document(write: DocumentWrite) -> KnowledgeDocument:
        service: AIService = app.state.ai
        return service.ingest(write, request_principal.get())

    @app.post("/api/v1/ai/ask", response_model=CopilotAnswer, responses=errors)
    def ai_ask(write: AskRequest) -> CopilotAnswer:
        service: AIService = app.state.ai
        return service.ask(write, request_principal.get())

    @app.get("/api/v1/ai/queries/{query_id}", response_model=QueryRun, responses=errors)
    def ai_query(query_id: UUID) -> QueryRun:
        service: AIService = app.state.ai
        return service.query(query_id, request_principal.get())

    @app.post("/api/v1/ai/feedback", response_model=FeedbackReceipt, responses=errors)
    def ai_feedback(write: FeedbackWrite) -> FeedbackReceipt:
        service: AIService = app.state.ai
        return service.feedback(write, request_principal.get())

    @app.get("/api/v1/sync", response_model=SyncSnapshot, responses=errors)
    def sync_snapshot() -> SyncSnapshot:
        runtime: TelemetryRuntime = app.state.telemetry
        return runtime.sync.snapshot(request_principal.get())

    @app.post("/api/v1/finance/tariffs", response_model=TariffVersion, responses=errors)
    def finance_tariff(write: TariffWrite) -> TariffVersion:
        runtime: TelemetryRuntime = app.state.telemetry
        return runtime.finance.tariff(write, request_principal.get())

    @app.post("/api/v1/finance/verifications", response_model=Verification, responses=errors)
    def finance_verification(write: VerificationRequest) -> Verification:
        runtime: TelemetryRuntime = app.state.telemetry
        return runtime.finance.start(write, request_principal.get())

    @app.get("/api/v1/finance/events", response_model=list[FinanceEvent], responses=errors)
    def finance_events(after: int = Query(default=0, ge=0)) -> list[FinanceEvent]:
        runtime: TelemetryRuntime = app.state.telemetry
        finance = runtime.finance
        finance.require(request_principal.get(), "finance.read", datetime.now(UTC))
        return finance.events(after)

    @app.get("/api/v1/dispatch/events", response_model=list[DispatchEvent], responses=errors)
    def dispatch_events(after: int = Query(default=0, ge=0)) -> list[DispatchEvent]:
        runtime: TelemetryRuntime = app.state.telemetry
        runtime.dispatch.require(request_principal.get(), "dispatch.read", datetime.now(UTC))
        return runtime.dispatch.events(after)

    @app.get("/api/v1/dispatch/{command_id}", response_model=DispatchDetail, responses=errors)
    def dispatch_detail(command_id: UUID) -> DispatchDetail:
        runtime: TelemetryRuntime = app.state.telemetry
        return runtime.dispatch.detail(command_id, request_principal.get())

    @app.post("/api/v1/dispatch/requests", response_model=DispatchCommand, responses=errors)
    def dispatch_request(write: ApprovalRequest) -> DispatchCommand:
        runtime: TelemetryRuntime = app.state.telemetry
        return runtime.dispatch.request(
            write,
            request_principal.get(),
            runtime.failed or runtime.scenario not in ("normal", "spike"),
        )

    @app.post("/api/v1/dispatch/decisions", response_model=DispatchCommand, responses=errors)
    def dispatch_decision(write: DecisionRequest) -> DispatchCommand:
        runtime: TelemetryRuntime = app.state.telemetry
        return runtime.dispatch.decide(
            write,
            request_principal.get(),
            runtime.failed or runtime.scenario not in ("normal", "spike"),
        )

    @app.get("/api/v1/optimization", response_model=OptimizationSnapshot, responses=errors)
    def optimization() -> OptimizationSnapshot:
        runtime: TelemetryRuntime = app.state.telemetry
        service: OptimizationService = app.state.optimization
        return service.snapshot(runtime.failed or runtime.scenario == "disconnected")

    @app.post("/api/v1/optimization/policies", response_model=OptimizationPolicy, responses=errors)
    def optimization_policy(write: PolicyWrite) -> OptimizationPolicy:
        service: OptimizationService = app.state.optimization
        return service.save_policy(write)

    @app.post("/api/v1/optimization/runs", response_model=OptimizationRun, responses=errors)
    def optimization_run(write: RunRequest) -> OptimizationRun:
        runtime: TelemetryRuntime = app.state.telemetry
        service: OptimizationService = app.state.optimization
        return service.run(write, runtime.failed or runtime.scenario == "disconnected")

    @app.get("/api/v1/optimization/runs", response_model=list[OptimizationRun], responses=errors)
    def optimization_history(
        before: int | None = Query(default=None, ge=1),
    ) -> list[OptimizationRun]:
        service: OptimizationService = app.state.optimization
        return service.history(before)

    @app.get(
        "/api/v1/optimization/events", response_model=list[OptimizationEvent], responses=errors
    )
    def optimization_events(after: int = Query(default=0, ge=0)) -> list[OptimizationEvent]:
        service: OptimizationService = app.state.optimization
        return service.events(after)

    @app.get("/api/v1/registry", response_model=RegistrySnapshot, responses=errors)
    def registry() -> RegistrySnapshot:
        runtime: TelemetryRuntime = app.state.telemetry
        return runtime.registry_snapshot()

    @app.get("/api/v1/intelligence", response_model=IntelligenceSnapshot, responses=errors)
    def intelligence() -> IntelligenceSnapshot:
        runtime: TelemetryRuntime = app.state.telemetry
        return runtime.forecasting.snapshot(runtime.failed or runtime.scenario == "disconnected")

    @app.get("/api/v1/forecasts", response_model=list[Prediction], responses=errors)
    def forecasts(before: int | None = Query(default=None, ge=1)) -> list[Prediction]:
        runtime: TelemetryRuntime = app.state.telemetry
        return runtime.forecasting.history(before)

    @app.get(
        "/api/v1/intelligence/events", response_model=list[IntelligenceEvent], responses=errors
    )
    def intelligence_events(after: int = Query(default=0, ge=0)) -> list[IntelligenceEvent]:
        runtime: TelemetryRuntime = app.state.telemetry
        return runtime.forecasting.events(after)

    @app.post("/api/v1/registry", response_model=RegistryRecord, responses=errors)
    def save_registry(write: RegistryWrite) -> RegistryRecord:
        runtime: TelemetryRuntime = app.state.telemetry
        return runtime.repo.registry.save(write)

    @app.get("/api/v1/registry/events", response_model=list[ConfigurationEvent], responses=errors)
    def registry_events(after: int = Query(default=0, ge=0)) -> list[ConfigurationEvent]:
        runtime: TelemetryRuntime = app.state.telemetry
        return runtime.repo.registry.events(after)

    @app.post("/api/v1/telemetry/batches", response_model=IngestResult, responses=errors)
    async def ingest(batch: TelemetryBatch) -> IngestResult:
        telemetry: TelemetryRuntime = app.state.telemetry
        return await telemetry.submit(batch)

    @app.get("/api/v1/telemetry/state", response_model=TelemetrySnapshot, responses=errors)
    def telemetry_state() -> TelemetrySnapshot:
        telemetry: TelemetryRuntime = app.state.telemetry
        return telemetry.snapshot()

    @app.get("/api/v1/telemetry", response_model=HistoryPage, responses=errors)
    def history(
        before: int | None = Query(default=None, ge=1),
        asset: str | None = Query(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$"),
        limit: int = Query(default=100, ge=1, le=100),
    ) -> HistoryPage:
        telemetry: TelemetryRuntime = app.state.telemetry
        points = telemetry.repo.history(before, asset, limit)
        return HistoryPage(
            points=points, next_cursor=points[-1].row_id if len(points) == limit else None
        )

    @app.post("/api/v1/simulator/scenario", response_model=ScenarioRequest, responses=errors)
    def scenario(body: ScenarioRequest) -> ScenarioRequest:
        app.state.telemetry.scenario = body.scenario
        return body

    @app.get("/api/v1/telemetry/events", response_model=list[TelemetryEvent], responses=errors)
    def events(after: int = Query(default=0, ge=0)) -> list[TelemetryEvent]:
        telemetry: TelemetryRuntime = app.state.telemetry
        return telemetry.repo.events(after)

    @app.get(
        "/api/v1/telemetry/stream",
        response_class=StreamingResponse,
        responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
    )
    async def stream(request: Request) -> StreamingResponse:
        viewer = request_principal.get()

        async def frames() -> AsyncIterator[str]:
            while not await request.is_disconnected():
                current = (
                    app.state.identity.current()
                    if identity_required and principal is None
                    else viewer
                )
                if current is None or current.actor != viewer.actor:
                    break
                try:
                    current.require(
                        "telemetry.read",
                        app.state.telemetry.repo.org_id,
                        app.state.telemetry.repo.facility_id,
                        datetime.now(UTC),
                    )
                except PermissionDenied:
                    break
                telemetry: TelemetryRuntime = app.state.telemetry
                snapshot = telemetry.snapshot()
                yield (
                    f"id: {snapshot.cursor}\nevent: snapshot\n"
                    f"data: {snapshot.model_dump_json()}\n\n"
                )
                await asyncio.sleep(1)

        return StreamingResponse(
            frames(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    return app
