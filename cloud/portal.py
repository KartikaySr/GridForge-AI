"""Browser-user API, separate from edge enrollment/transport credentials."""

import os
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit
from uuid import UUID

import uvicorn
from fastapi import FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from cloud.repository import CloudRepository
from services.portal.contracts import PortalHistory, PortalIdentity, PortalLogin, Portfolio
from services.portal.service import PortalDenied, PortalService
from services.sync.contracts import Stream

COOKIE = "gridforge_portal_session"


def create_portal_app(
    dsn: str, origin: str, *, secure: bool = True, migrate: bool = True
) -> FastAPI:
    parsed = urlsplit(origin)
    if parsed.path or parsed.query or parsed.fragment or parsed.username or not parsed.hostname:
        raise ValueError("One exact web origin is required")
    if not secure and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("Insecure cookies are restricted to loopback development")
    if parsed.scheme != ("https" if secure else "http"):
        raise ValueError("Origin scheme must match cookie security")
    service = PortalService(dsn)
    if migrate:
        CloudRepository(dsn).migrate()
        service.migrate()
    app = FastAPI(
        title="GridForge Web Portal",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.portal = service

    @app.middleware("http")
    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if (request.headers.get("origin") and request.headers["origin"] != origin) or (
            request.method == "POST" and request.headers.get("origin") != origin
        ):
            return JSONResponse(status_code=403, content={"code": "ORIGIN_DENIED"})
        if request.method == "POST":
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 4096:
                    return JSONResponse(status_code=413, content={"code": "BODY_TOO_LARGE"})
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"code": "INVALID_PORTAL_REQUEST"})

    @app.exception_handler(PortalDenied)
    async def denied(request: Request, exc: PortalDenied) -> JSONResponse:
        code = str(exc)
        return JSONResponse(
            status_code=429
            if code == "LOGIN_RATE_LIMIT"
            else 404
            if code == "FACILITY_UNAVAILABLE"
            else 401,
            content={"code": code},
        )

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ready", "mode": "SIMULATION", "scope": "portal-process"}

    @app.post("/api/v1/login", response_model=PortalIdentity)
    def login(write: PortalLogin, response: Response) -> PortalIdentity:
        token, identity = service.login(write)
        response.set_cookie(
            COOKIE,
            token,
            max_age=3600,
            secure=secure,
            httponly=True,
            samesite="strict",
            path="/api/v1",
        )
        return identity

    @app.post("/api/v1/logout")
    def logout(request: Request, response: Response) -> dict[str, bool]:
        service.logout(request.cookies.get(COOKIE))
        response.delete_cookie(
            COOKIE, path="/api/v1", secure=secure, httponly=True, samesite="strict"
        )
        return {"signed_out": True}

    @app.get("/api/v1/me", response_model=PortalIdentity)
    def me(request: Request) -> PortalIdentity:
        return service.identity(request.cookies.get(COOKIE))

    @app.get("/api/v1/portfolio", response_model=Portfolio)
    def portfolio(request: Request) -> Portfolio:
        return service.portfolio(service.identity(request.cookies.get(COOKIE)))

    @app.get("/api/v1/facilities/{edge_id}/events", response_model=PortalHistory)
    def events(
        request: Request,
        edge_id: UUID,
        stream: Stream = "telemetry",
        before: int = Query(default=9223372036854775807, ge=1, le=9223372036854775807),
    ) -> PortalHistory:
        return service.history(
            service.identity(request.cookies.get(COOKIE)), edge_id, stream, before
        )

    return app


def main() -> None:
    origin = os.environ.get("GRIDFORGE_WEB_ORIGIN", "http://127.0.0.1:5174")
    app = create_portal_app(
        os.environ["GRIDFORGE_CLOUD_DATABASE_URL"], origin, secure=not origin.startswith("http://")
    )
    uvicorn.run(
        app,
        host=os.environ.get("GRIDFORGE_PORTAL_HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8082")),
        proxy_headers=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
