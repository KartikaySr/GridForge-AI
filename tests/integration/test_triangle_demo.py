import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cloud.portal import create_portal_app
from edge.runtime.telemetry import TelemetryRuntime
from scripts.demo_cloud import receiver
from scripts.triangle_demo import prepare
from services.demonstration.service import DemoService
from services.portal.contracts import PortalLogin
from services.portal.service import PortalService
from services.sync.codec import STREAMS
from services.sync.service import HttpCloudTransport
from tests.integration.test_sync_postgres import postgres  # noqa: F401


def test_shared_factory_live_sync_and_mobile_report_roundtrip(
    postgres: str,  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    demo = DemoService()
    try:
        with receiver(demo, postgres):
            prepare(demo, postgres, tmp_path)
            login = json.loads((tmp_path / "login.json").read_text())
            assert (tmp_path / "login.json").stat().st_mode & 0o777 == 0o600
            portal = PortalService(postgres)
            _, user = portal.login(
                PortalLogin(username=login["portal_username"], password=login["password"])
            )
            for stream in STREAMS:
                assert portal.history(user, demo.repo.edge_id, stream, 2**63 - 1).events
            assert demo.network and isinstance(demo.network.transport, HttpCloudTransport)
            monkeypatch.setenv("GRIDFORGE_CLOUD_URL", demo.network.transport.url)
            monkeypatch.setenv("GRIDFORGE_EDGE_TOKEN", demo.sync.token or "")
            start = datetime.now(UTC)

            async def live() -> None:
                runtime = TelemetryRuntime(tmp_path / "edge.db")
                assert runtime.repo.edge_id == demo.repo.edge_id
                assert (
                    runtime.repo.db.execute("SELECT count(*) FROM production_reports").fetchone()[0]
                    == 2
                )
                assert runtime.repo.db.execute("SELECT count(*) FROM incidents").fetchone()[0] > 0
                await runtime.start()
                try:
                    for _ in range(50):
                        await asyncio.sleep(0.1)
                        events = portal.history(
                            user, demo.repo.edge_id, "telemetry", 2**63 - 1
                        ).events
                        if datetime.fromisoformat(events[0].body["occurred_at"]) >= start:
                            break
                    else:
                        pytest.fail("Native runtime telemetry never reached the shared cloud")
                finally:
                    await runtime.close()

            asyncio.run(live())
            origin = "http://127.0.0.1:5174"
            with TestClient(create_portal_app(postgres, origin, secure=False)) as client:
                credentials = {"username": login["portal_username"], "password": login["password"]}
                client.post(
                    "/api/v1/login", json=credentials, headers={"Origin": origin}
                ).raise_for_status()
                session = client.post("/api/v1/mobile/login", json=credentials).json()
                headers = {"Authorization": "Bearer " + session["token"]}
                note = {
                    "request_id": str(uuid4()),
                    "edge_id": str(demo.repo.edge_id),
                    "text": "Synthetic triangle observation",
                }
                client.post("/api/v1/mobile/reports", json=note, headers=headers).raise_for_status()
                client.post("/api/v1/mobile/reports", json=note, headers=headers).raise_for_status()
                route = f"/facilities/{demo.repo.edge_id}/reports"
                web = client.get("/api/v1" + route)
                mobile = client.get("/api/v1/mobile" + route, headers=headers)
                assert web.status_code == mobile.status_code == 200
                assert web.json() == mobile.json()
                assert len(web.json()["reports"]) == 2
                assert client.get(f"/api/v1/facilities/{uuid4()}/reports").status_code == 404
    finally:
        demo.close()
