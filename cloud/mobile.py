"""Native bearer transport. Browser cookies cannot authorize mobile requests."""

from uuid import UUID

from fastapi import APIRouter, Query, Request

from services.portal.contracts import (
    FieldReportHistory,
    FieldReportReceipt,
    FieldReportWrite,
    MobileSession,
    PortalHistory,
    PortalIdentity,
    PortalLogin,
    Portfolio,
)
from services.portal.reports import receive_report, report_history
from services.portal.service import PortalService
from services.sync.contracts import Stream


def mobile_router(dsn: str) -> APIRouter:
    router = APIRouter(prefix="/api/v1/mobile")
    service = PortalService(dsn, client="mobile")

    def token(request: Request) -> str | None:
        value = request.headers.get("authorization", "")
        return value[7:] if value.startswith("Bearer ") else None

    def identity(request: Request) -> PortalIdentity:
        return service.identity(token(request))

    @router.post("/login", response_model=MobileSession)
    def login(write: PortalLogin) -> MobileSession:
        secret, user = service.login(write)
        return MobileSession(token=secret, identity=user)

    @router.get("/me", response_model=PortalIdentity)
    def me(request: Request) -> PortalIdentity:
        return identity(request)

    @router.post("/logout")
    def logout(request: Request) -> dict[str, bool]:
        service.logout(token(request))
        return {"signed_out": True}

    @router.get("/portfolio", response_model=Portfolio)
    def portfolio(request: Request) -> Portfolio:
        return service.portfolio(identity(request))

    @router.get("/facilities/{edge_id}/events", response_model=PortalHistory)
    def events(
        request: Request,
        edge_id: UUID,
        stream: Stream = "telemetry",
        before: int = Query(default=9223372036854775807, ge=1, le=9223372036854775807),
    ) -> PortalHistory:
        return service.history(identity(request), edge_id, stream, before)

    @router.post("/reports", response_model=FieldReportReceipt)
    def report(request: Request, write: FieldReportWrite) -> FieldReportReceipt:
        return receive_report(dsn, identity(request), write)

    @router.get("/facilities/{edge_id}/reports", response_model=FieldReportHistory)
    def reports(request: Request, edge_id: UUID) -> FieldReportHistory:
        return report_history(dsn, identity(request), edge_id)

    return router
