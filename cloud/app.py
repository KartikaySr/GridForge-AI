"""PostgreSQL-backed, append-only cloud visibility endpoint. No dispatch endpoint exists."""

from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import FastAPI, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from cloud.repository import CloudRejected, CloudRepository
from services.sync.contracts import CloudSyncState, SyncAck, SyncBatch


def create_cloud_app(dsn: str, *, migrate: bool = True) -> FastAPI:
    repository = CloudRepository(dsn)
    if migrate:
        repository.migrate()
    app = FastAPI(title="GridForge Cloud Sync", version="1.0.0", docs_url=None, redoc_url=None)
    app.state.repository = repository

    @app.middleware("http")
    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if (
            request.headers.get("origin")
            or not request.headers.get("authorization", "").startswith("Bearer ")
            or not request.headers.get("x-edge-id")
        ):
            return JSONResponse(status_code=401, content={"code": "EDGE_AUTH_DENIED"})
        if request.method == "POST":
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 65536:
                    return JSONResponse(status_code=413, content={"code": "BATCH_TOO_LARGE"})
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    def credentials(raw_id: str, authorization: str) -> tuple[UUID, str]:
        token = authorization[7:]
        if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
            raise CloudRejected("EDGE_AUTH_DENIED")
        try:
            return UUID(raw_id), token
        except ValueError:
            raise CloudRejected("EDGE_AUTH_DENIED") from None

    @app.exception_handler(CloudRejected)
    async def conflict(request: Request, exc: CloudRejected) -> JSONResponse:
        return JSONResponse(
            status_code=401 if exc.code == "EDGE_AUTH_DENIED" else 409,
            content={"code": exc.code},
        )

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"code": "INVALID_SYNC_BATCH"})

    @app.get("/api/v1/sync/state", response_model=CloudSyncState)
    def state(
        x_edge_id: str = Header(alias="X-Edge-ID"),
        authorization: str = Header(alias="Authorization"),
    ) -> CloudSyncState:
        edge_id, token = credentials(x_edge_id, authorization)
        return repository.state(edge_id, token)

    @app.post("/api/v1/sync/batches", response_model=SyncAck)
    def upload(
        batch: SyncBatch,
        x_edge_id: str = Header(alias="X-Edge-ID"),
        authorization: str = Header(alias="Authorization"),
    ) -> SyncAck:
        edge_id, token = credentials(x_edge_id, authorization)
        if edge_id != batch.edge_id:
            raise CloudRejected("EDGE_AUTH_DENIED")
        return repository.apply(batch, token)

    return app
