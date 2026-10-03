"""Disposable real PostgreSQL and HTTP receiver for the simulation acceptance rehearsal."""

import asyncio
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import uvicorn

from cloud.app import create_cloud_app
from cloud.repository import CloudRepository
from services.demonstration.service import DemoService
from services.sync.service import HttpCloudTransport


@contextmanager
def local_postgres() -> Iterator[str]:
    initdb, pg_ctl = shutil.which("initdb"), shutil.which("pg_ctl")
    if not initdb or not pg_ctl:
        raise RuntimeError("Install PostgreSQL test tools and add its bin directory to PATH.")
    with tempfile.TemporaryDirectory(prefix="gridforge-demo-pg-") as directory:
        data = Path(directory) / "data"
        subprocess.run(
            [initdb, "-D", str(data), "-A", "trust", "-U", "gridforge_demo", "--no-instructions"],
            check=True,
            capture_output=True,
        )
        with socket.socket() as port_socket:
            port_socket.bind(("127.0.0.1", 0))
            port = port_socket.getsockname()[1]
        subprocess.run(
            [
                pg_ctl,
                "-D",
                str(data),
                "-l",
                str(Path(directory) / "server.log"),
                "-o",
                f"-h 127.0.0.1 -p {port} -k {directory}",
                "start",
            ],
            check=True,
            capture_output=True,
        )
        try:
            yield f"host=127.0.0.1 port={port} dbname=postgres user=gridforge_demo"
        finally:
            subprocess.run(
                [pg_ctl, "-D", str(data), "-m", "immediate", "stop"],
                check=True,
                capture_output=True,
            )


@contextmanager
def receiver(demo: DemoService, dsn: str) -> Iterator[CloudRepository]:
    cloud = CloudRepository(dsn)
    cloud.migrate()
    token = secrets.token_hex(32)
    cloud.enroll(demo.repo.edge_id, demo.repo.org_id, demo.repo.facility_id, token)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(create_cloud_app(dsn), log_level="critical", access_log=False)
        )
        thread = threading.Thread(
            target=lambda: asyncio.run(server.serve(sockets=[listener])), daemon=True
        )
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Demo cloud did not start")
                time.sleep(0.02)
            demo.connect(HttpCloudTransport(f"http://127.0.0.1:{port}"), token)
            yield cloud
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError("Demo cloud did not stop")
