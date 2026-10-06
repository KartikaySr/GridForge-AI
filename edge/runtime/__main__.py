"""Native-owned child process. Credentials enter only through its private stdin pipe."""

import asyncio
import json
import socket
import sys
import threading
from pathlib import Path
from uuid import UUID

import uvicorn
from pydantic import BaseModel, ConfigDict, Field

from edge.runtime.app import create_app
from edge.runtime.ownership import database_owner


class Bootstrap(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol: int = Field(ge=1, le=1)
    token: str = Field(pattern=r"^[0-9a-f]{64}$")
    instance_id: UUID
    db_path: Path | None = None


def main() -> int:
    try:
        bootstrap = Bootstrap.model_validate_json(sys.stdin.buffer.readline(4097))
    except Exception:
        print('{"event":"bootstrap.invalid"}', file=sys.stderr, flush=True)
        return 2

    with database_owner(bootstrap.db_path):
        return serve(bootstrap)


def serve(bootstrap: Bootstrap) -> int:
    app = create_app(bootstrap.token, bootstrap.instance_id, bootstrap.db_path)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.setblocking(False)
    port = listener.getsockname()[1]

    class Server(uvicorn.Server):
        async def startup(self, sockets: list[socket.socket] | None = None) -> None:
            await super().startup(sockets=sockets)
            if self.started:
                print(
                    json.dumps(
                        {
                            "event": "runtime_ready",
                            "protocol": 1,
                            "port": port,
                            "instance_id": str(bootstrap.instance_id),
                        }
                    ),
                    flush=True,
                )

    server = Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_config=None,
            log_level="critical",
            access_log=False,
            server_header=False,
            proxy_headers=False,
            timeout_graceful_shutdown=2,
            limit_concurrency=16,
        )
    )

    def watch_parent() -> None:
        # EOF handles parent crash; any control message requests graceful shutdown.
        # It is a private pipe, never exposed as an HTTP mutation endpoint.
        sys.stdin.buffer.readline(4097)
        server.should_exit = True

    threading.Thread(target=watch_parent, daemon=True).start()
    try:
        asyncio.run(server.serve(sockets=[listener]))
    finally:
        listener.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print('{"event":"runtime.failed"}', file=sys.stderr, flush=True)
        raise SystemExit(1) from None
