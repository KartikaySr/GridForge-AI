import json
import secrets
import socket
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cloud.app import create_cloud_app
from edge.storage.repository import Repository
from services.dispatch.permissions import Principal
from services.sync.service import HttpCloudTransport, SyncFailure, SyncService
from simulator.factory import factory_batch
from tests.support import create_app


def test_edge_identity_and_v6_upgrade_preserve_outboxes(tmp_path: Path) -> None:
    path = tmp_path / "edge.db"
    repo = Repository(path)
    now = datetime.now(UTC)
    repo.ingest(factory_batch(repo.org_id, repo.facility_id, repo.seed, 1, now, "normal"), now)
    edge_id, org_id, facility_id = repo.edge_id, repo.org_id, repo.facility_id
    count = repo.db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
    repo.close()
    reopened = Repository(path)
    assert reopened.edge_id == edge_id
    reopened.db.executescript(
        "DROP TABLE production_reports; "
        "DROP TABLE sync_conflicts; DROP TABLE sync_streams; DROP TABLE edge_identity; "
        "PRAGMA user_version=6;"
    )
    reopened.close()
    upgraded = Repository(path)
    assert upgraded.db.execute("PRAGMA user_version").fetchone()[0] == 10
    assert (upgraded.org_id, upgraded.facility_id) == (org_id, facility_id)
    assert upgraded.db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == count
    assert upgraded.db.execute("SELECT COUNT(*) FROM sync_streams").fetchone()[0] == 7
    assert upgraded.edge_id != edge_id  # A v6 store had no provisioned edge identity.
    upgraded.close()


def test_cloud_openapi_contract_is_generated_from_receiver() -> None:
    schema = create_cloud_app("", migrate=False).openapi()
    schema["components"]["securitySchemes"] = {"EdgeToken": {"type": "http", "scheme": "bearer"}}
    schema["security"] = [{"EdgeToken": []}]
    path = Path(__file__).parents[2] / "packages/api-client/cloud.openapi.json"
    assert json.loads(path.read_text()) == schema


def test_sync_snapshot_auth_offline_and_pending_age(tmp_path: Path) -> None:
    path = tmp_path / "edge.db"
    repo = Repository(path)
    org_id, facility_id = repo.org_id, repo.facility_id
    repo.close()
    viewer = Principal(
        "viewer",
        org_id,
        facility_id,
        frozenset({"sync.read"}),
        datetime.now(UTC) + timedelta(hours=1),
    )
    headers = {"Authorization": "Bearer " + "a" * 64}
    with TestClient(
        create_app("a" * 64, uuid4(), path, simulate=False, principal=viewer)
    ) as client:
        assert client.get("/api/v1/sync").status_code == 401
        result = client.get("/api/v1/sync", headers=headers)
        assert result.status_code == 200
        body = result.json()
        assert body["state"] == "NOT_CONFIGURED"
        assert body["configured"] is False
        assert body["pending_count"] > 0  # Registry bootstrap events are durable.
        assert body["oldest_pending_age_seconds"] is not None
        assert len(body["streams"]) == 7
        assert (
            client.get("/api/v1/sync", headers=headers | {"Origin": "https://evil"}).status_code
            == 401
        )
    denied = Principal(
        "viewer", org_id, facility_id, frozenset(), datetime.now(UTC) + timedelta(hours=1)
    )
    with TestClient(
        create_app("a" * 64, uuid4(), path, simulate=False, principal=denied)
    ) as client:
        assert client.get("/api/v1/sync", headers=headers).status_code == 403


def test_client_url_and_local_sequence_gap_fail_closed() -> None:
    with pytest.raises(ValueError):
        HttpCloudTransport("http://example.com")
    HttpCloudTransport("https://example.com")
    HttpCloudTransport("http://127.0.0.1:8081")
    repo = Repository(None)
    now = datetime.now(UTC)
    repo.ingest(factory_batch(repo.org_id, repo.facility_id, repo.seed, 1, now, "normal"), now)
    with repo.lock, repo.db:
        repo.db.execute("DELETE FROM outbox WHERE id=3")
    service = SyncService(repo)
    with pytest.raises(SyncFailure, match="LOCAL_SEQUENCE_GAP"):
        service.pending_batch("telemetry")
    assert (
        service.snapshot(
            Principal(
                "viewer",
                repo.org_id,
                repo.facility_id,
                frozenset({"sync.read"}),
                now + timedelta(hours=1),
            ),
            now,
        )
        .streams[0]
        .acknowledged_sequence
        == 0
    )
    repo.close()


def test_local_runtime_ingests_while_configured_cloud_is_down(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "offline.db"
    repo = Repository(path)
    now = datetime.now(UTC)
    batch = factory_batch(repo.org_id, repo.facility_id, repo.seed, 1, now, "normal")
    repo.close()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    monkeypatch.setenv("GRIDFORGE_CLOUD_URL", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("GRIDFORGE_EDGE_TOKEN", secrets.token_hex(32))
    headers = {"Authorization": "Bearer " + "a" * 64}
    with TestClient(create_app("a" * 64, uuid4(), path, simulate=False)) as client:
        assert (
            client.post(
                "/api/v1/telemetry/batches", headers=headers, json=batch.model_dump(mode="json")
            ).json()["accepted"]
            == 5
        )
        status = client.get("/api/v1/sync", headers=headers).json()
        for _ in range(20):
            if status["state"] == "OFFLINE":
                break
            time.sleep(0.05)
            status = client.get("/api/v1/sync", headers=headers).json()
        assert status["state"] == "OFFLINE"
        assert status["configured"] is True
        assert status["pending_count"] >= 5
        assert client.get("/api/v1/system/health", headers=headers).json()["status"] == "READY"
    retained = Repository(path)
    assert retained.db.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0] == 5
    assert (
        retained.db.execute("SELECT COUNT(*) FROM outbox WHERE acknowledged=0").fetchone()[0] == 5
    )
    retained.close()
