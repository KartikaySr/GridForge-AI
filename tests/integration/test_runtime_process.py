"""Real loopback/process checks. No OT, database, cloud, or fabricated readiness."""

import json
import secrets
import subprocess
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from services.telemetry.contracts import TelemetrySnapshot

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[tuple[subprocess.Popen[str], str, str]]:
    token = secrets.token_hex(32)
    process = subprocess.Popen(
        [sys.executable, "-u", "-m", "edge.runtime"],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdin is not None and process.stdout is not None
    try:
        process.stdin.write(
            json.dumps(
                {
                    "protocol": 1,
                    "token": token,
                    "instance_id": str(uuid4()),
                    "db_path": str(tmp_path / "edge.db"),
                }
            )
            + "\n"
        )
        process.stdin.flush()
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(process.stdout.readline)
            try:
                line = pending.result(timeout=10)
            except TimeoutError:
                process.kill()
                raise
        ready = json.loads(line)
        assert ready["event"] == "runtime_ready"
        assert token not in line
        response = httpx.post(
            f"http://127.0.0.1:{ready['port']}/api/v1/identity/bootstrap",
            headers={"Authorization": f"Bearer {token}"},
            json={"username": "test-admin", "password": secrets.token_hex(16)},
            trust_env=False,
            timeout=5,
        )
        assert response.status_code == 200
        yield process, f"http://127.0.0.1:{ready['port']}", token
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()


def test_real_authenticated_http_and_graceful_shutdown(
    runtime: tuple[subprocess.Popen[str], str, str],
) -> None:
    process, base, token = runtime
    with httpx.Client(base_url=base, trust_env=False, timeout=2) as client:
        assert client.get("/api/v1/system/health").status_code == 401
        health = client.get("/api/v1/system/health", headers={"Authorization": f"Bearer {token}"})
        assert health.status_code == 200
        assert health.json()["status"] == "READY"
        assert process.stdin is not None
        process.stdin.write("shutdown\n")
        process.stdin.flush()
        assert process.wait(timeout=5) == 0
        with pytest.raises(httpx.ConnectError):
            client.get("/api/v1/system/health")


def test_parent_pipe_loss_stops_runtime(runtime: tuple[subprocess.Popen[str], str, str]) -> None:
    process, _, _ = runtime
    assert process.stdin is not None
    process.stdin.close()
    assert process.wait(timeout=5) == 0


def test_malformed_bootstrap_fails_without_echoing_secret() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "edge.runtime"],
        cwd=ROOT,
        input='{"token":"do-not-log-me"}\n',
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 2
    assert "do-not-log-me" not in result.stdout + result.stderr


def test_openapi_matches_committed_schema() -> None:
    from edge.runtime.app import create_app

    schema = create_app(secrets.token_hex(32), uuid4()).openapi()
    committed = json.loads((ROOT / "packages/api-client/runtime.openapi.json").read_text())
    # Transport security declarations are added by the schema exporter; compare executable shapes.
    assert schema["paths"] == committed["paths"]
    assert schema["components"]["schemas"] == committed["components"]["schemas"]


def test_live_sse_snapshot_reconnect(runtime: tuple[subprocess.Popen[str], str, str]) -> None:
    _, base, token = runtime
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=base, headers=headers, trust_env=False, timeout=5) as client:

        def read_frame() -> TelemetrySnapshot:
            with client.stream("GET", "/api/v1/telemetry/stream") as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("text/event-stream")
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        result = TelemetrySnapshot.model_validate_json(line[6:])
                        return result
            raise AssertionError("No SSE snapshot")

        first = read_frame()
        assert first.mode == "SIMULATION"
        assert len(first.assets) == 5
        client.post("/api/v1/simulator/scenario", json={"scenario": "disconnected"})
        disconnected = read_frame()
        assert disconnected.scenario == "disconnected"
        assert all(a.status == "DISCONNECTED" for a in disconnected.assets)
        client.post("/api/v1/simulator/scenario", json={"scenario": "normal"})
        recovered = read_frame()
        assert recovered.facility_id == first.facility_id
        assert recovered.scenario == "normal"
