"""Exercise the frozen runtime outside the repository with a clean environment."""

import argparse
import json
import secrets
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import httpx


def smoke(executable: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="gridforge-package-smoke-") as directory:
        token = secrets.token_hex(32)
        process = subprocess.Popen(
            [str(executable.resolve(strict=True))],
            cwd=directory,
            env={"PATH": "/usr/bin:/bin"},
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
                        "db_path": str(Path(directory) / "edge.db"),
                    }
                )
                + "\n"
            )
            process.stdin.flush()
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(process.stdout.readline)
                try:
                    line = future.result(timeout=30)
                except TimeoutError:
                    process.kill()
                    raise
            ready = json.loads(line)
            assert ready["event"] == "runtime_ready"
            with httpx.Client(
                base_url=f"http://127.0.0.1:{ready['port']}",
                headers={"Authorization": f"Bearer {token}"},
                trust_env=False,
                timeout=15,
            ) as client:
                assert client.get("/api/v1/registry").status_code == 403
                response = client.post(
                    "/api/v1/identity/bootstrap",
                    json={"username": "package-smoke", "password": secrets.token_hex(16)},
                )
                assert response.status_code == 200, response.text
                assert client.get("/api/v1/registry").status_code == 200
                demo = client.get("/api/v1/demo").json()
                assert demo["clock"] == "ACCELERATED_ISOLATED"
                for action in ["normal", "bad", "peak", "propose", "approve", "verify", "explain"]:
                    response = client.post(
                        "/api/v1/demo", json={"request_id": str(uuid4()), "action": action}
                    )
                    assert response.status_code == 200, response.text
                assert response.json()["verification"]["status"] == "VERIFIED"
                assert response.json()["explanation"]["evidence"]
                assert client.get("/api/v1/system/bundle").json()["audit"]["integrity_ok"]
                assert client.post("/api/v1/identity/logout").status_code == 200
                assert client.get("/api/v1/registry").status_code == 403
            process.stdin.write("shutdown\n")
            process.stdin.flush()
            assert process.wait(timeout=10) == 0
            print(
                "PASS: frozen runtime, clean environment, scoped sign-in, "
                "diagnostics, logout, shutdown"
            )
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    smoke(parser.parse_args().executable)


if __name__ == "__main__":
    main()
