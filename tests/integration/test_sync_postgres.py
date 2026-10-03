"""Real PostgreSQL transaction, replay and reconnect checks; skipped without local PG tools."""

import asyncio
import os
import secrets
import shutil
import socket
import subprocess
import threading
import time
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
import uvicorn
from fastapi.testclient import TestClient

from cloud.app import create_cloud_app
from cloud.repository import CloudRejected, CloudRepository
from edge.storage.repository import Repository
from services.dispatch.contracts import ApprovalRequest
from services.dispatch.permissions import SIMULATION_PERMISSIONS, Principal
from services.dispatch.service import DispatchService
from services.finance.service import FinanceService
from services.forecasting.service import ForecastService
from services.sync.codec import digest
from services.sync.contracts import CloudSyncState, SyncAck, SyncBatch, SyncEntry
from services.sync.service import SyncFailure, SyncService
from simulator.factory import factory_batch
from tests.unit.test_finance import tariff_write
from tests.unit.test_forecasting import ORIGIN
from tests.unit.test_optimization import setup


@pytest.fixture(scope="module")
def postgres(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    initdb, pg_ctl = shutil.which("initdb"), shutil.which("pg_ctl")
    if not initdb or not pg_ctl:
        pytest.skip("PostgreSQL test binaries are unavailable")
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("initdb cannot run as root")
    base = tmp_path_factory.mktemp("gridforge-postgres")
    data = base / "data"
    subprocess.run(
        [initdb, "-D", str(data), "-A", "trust", "-U", "gridforge_test", "--no-instructions"],
        check=True,
        capture_output=True,
        text=True,
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    subprocess.run(
        [
            pg_ctl,
            "-D",
            str(data),
            "-l",
            str(base / "postgres.log"),
            "-o",
            f"-h 127.0.0.1 -p {port} -k /tmp",
            "start",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        yield f"host=127.0.0.1 port={port} dbname=postgres user=gridforge_test"
    finally:
        subprocess.run(
            [pg_ctl, "-D", str(data), "-m", "immediate", "stop"],
            check=True,
            capture_output=True,
            text=True,
        )


class DirectTransport:
    def __init__(self, cloud: CloudRepository) -> None:
        self.cloud = cloud
        self.offline = False
        self.lose_one_ack = False

    def state(self, edge_id: UUID, token: str) -> CloudSyncState:
        if self.offline:
            raise SyncFailure("CLOUD_UNAVAILABLE")
        return self.cloud.state(edge_id, token)

    def upload(self, batch: SyncBatch, token: str) -> SyncAck:
        if self.offline:
            raise SyncFailure("CLOUD_UNAVAILABLE")
        try:
            ack = self.cloud.apply(batch, token)
        except CloudRejected as error:
            raise SyncFailure(error.code, batch.stream, error.sequence) from None
        if self.lose_one_ack:
            self.lose_one_ack = False
            raise SyncFailure("CLOUD_UNAVAILABLE")
        return ack


def enroll(cloud: CloudRepository, repo: Repository) -> str:
    token = secrets.token_hex(32)
    cloud.enroll(repo.edge_id, repo.org_id, repo.facility_id, token)
    return token


def cloud_count(conn: psycopg.Connection, sql: str, edge_id: UUID) -> int:
    row = conn.execute(sql, (edge_id,)).fetchone()
    assert row is not None
    return int(row[0])


def test_production_http_transport_round_trip(postgres: str) -> None:
    cloud = CloudRepository(postgres)
    cloud.migrate()
    repo = Repository(None)
    token = enroll(cloud, repo)
    repo.ingest(
        factory_batch(repo.org_id, repo.facility_id, repo.seed, 1, ORIGIN, "normal"), ORIGIN
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            create_cloud_app(postgres),
            host="127.0.0.1",
            port=port,
            log_level="critical",
            access_log=False,
        )
    )
    thread = threading.Thread(target=lambda: asyncio.run(server.serve()), daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.02)
        assert server.started
        service = SyncService(repo, url=f"http://127.0.0.1:{port}", token=token)
        service.tick(ORIGIN)
        assert service.state == "SYNCHRONIZED"
        assert service.pending_count() == 0
        with psycopg.connect(postgres) as conn:
            assert (
                cloud_count(
                    conn,
                    "SELECT COUNT(*) FROM sync_events WHERE edge_id=%s AND stream='telemetry'",
                    repo.edge_id,
                )
                == 5
            )
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        repo.close()


def test_cloud_http_auth_replay_and_conflict(postgres: str) -> None:
    cloud = CloudRepository(postgres)
    cloud.migrate()
    repo = Repository(None)
    token = enroll(cloud, repo)
    repo.ingest(
        factory_batch(repo.org_id, repo.facility_id, repo.seed, 1, ORIGIN, "normal"), ORIGIN
    )
    service = SyncService(repo, token=token, transport=DirectTransport(cloud))
    batch = service.pending_batch("telemetry")
    assert batch and len(batch.entries) == 5
    headers = {"Authorization": f"Bearer {token}", "X-Edge-ID": str(repo.edge_id)}
    with TestClient(create_cloud_app(postgres)) as client:
        assert client.get("/api/v1/sync/state").status_code == 401
        assert client.get("/api/v1/sync/state", headers=headers).json()["edge_id"] == str(
            repo.edge_id
        )
        body = batch.model_dump(mode="json")
        first = client.post("/api/v1/sync/batches", headers=headers, json=body)
        assert first.status_code == 200 and first.json()["accepted"] == 5
        replay = client.post("/api/v1/sync/batches", headers=headers, json=body)
        assert replay.status_code == 200 and replay.json()["replayed"] == 5
        changed = batch.entries[0].body | {"event_type": "Changed"}
        conflicted = batch.model_copy(
            update={
                "entries": [
                    batch.entries[0].model_copy(update={"body": changed, "digest": digest(changed)})
                ]
            }
        )
        response = client.post(
            "/api/v1/sync/batches", headers=headers, json=conflicted.model_dump(mode="json")
        )
        assert response.status_code == 409 and response.json()["code"] == "REPLAY_CONFLICT"
        valid_body = batch.entries[0].body | {"event_id": str(uuid4())}
        valid_entry = SyncEntry(
            sequence=6,
            event_id=UUID(valid_body["event_id"]),
            digest=digest(valid_body),
            body=valid_body,
        )
        gap_body = batch.entries[1].body | {"event_id": str(uuid4())}
        gap_entry = SyncEntry(
            sequence=8,
            event_id=UUID(gap_body["event_id"]),
            digest=digest(gap_body),
            body=gap_body,
        )
        atomic = batch.model_copy(update={"entries": [valid_entry, gap_entry]})
        response = client.post(
            "/api/v1/sync/batches", headers=headers, json=atomic.model_dump(mode="json")
        )
        assert response.status_code == 409 and response.json()["code"] == "SEQUENCE_GAP"
        nested = batch.entries[0].body | {
            "payload": batch.entries[0].body["payload"] | {"facility_id": str(uuid4())}
        }
        cross_scope = batch.model_copy(
            update={
                "entries": [
                    batch.entries[0].model_copy(update={"body": nested, "digest": digest(nested)})
                ]
            }
        )
        response = client.post(
            "/api/v1/sync/batches", headers=headers, json=cross_scope.model_dump(mode="json")
        )
        assert response.status_code == 409
        assert response.json()["code"] == "EVENT_CONTRACT_OR_SCOPE_CONFLICT"
        assert (
            client.post(
                "/api/v1/sync/batches", headers=headers | {"Origin": "https://evil"}, json=body
            ).status_code
            == 401
        )
        assert (
            client.get(
                "/api/v1/sync/state",
                headers={
                    "Authorization": "Bearer " + secrets.token_hex(32),
                    "X-Edge-ID": str(repo.edge_id),
                },
            ).status_code
            == 401
        )
    with psycopg.connect(postgres) as conn:
        assert (
            cloud_count(conn, "SELECT COUNT(*) FROM sync_events WHERE edge_id=%s", repo.edge_id)
            == 5
        )
        assert (
            cloud_count(
                conn, "SELECT COUNT(*) FROM sync_conflict_audit WHERE edge_id=%s", repo.edge_id
            )
            == 3
        )
    repo.close()


def test_offline_continuity_lost_ack_reconnect_without_duplicate(
    postgres: str, tmp_path: Path
) -> None:
    cloud = CloudRepository(postgres)
    path = tmp_path / "edge.db"
    repo = Repository(path)
    token = enroll(cloud, repo)
    transport = DirectTransport(cloud)
    service = SyncService(repo, token=token, transport=transport)
    transport.offline = True
    repo.ingest(
        factory_batch(repo.org_id, repo.facility_id, repo.seed, 1, ORIGIN, "normal"), ORIGIN
    )
    service.tick(ORIGIN)
    assert service.state == "OFFLINE" and service.pending_count() >= 5
    initial_pending = service.pending_count()
    repo.ingest(
        factory_batch(
            repo.org_id, repo.facility_id, repo.seed, 2, ORIGIN + timedelta(seconds=1), "normal"
        ),
        ORIGIN + timedelta(seconds=1),
    )
    assert service.pending_count() == initial_pending + 5
    transport.offline = False
    transport.lose_one_ack = True
    service.tick(ORIGIN + timedelta(seconds=2))
    assert service.state == "OFFLINE" and service.pending_count() == initial_pending + 5
    service.tick(ORIGIN + timedelta(seconds=4))
    assert (
        service.snapshot(
            Principal(
                "viewer",
                repo.org_id,
                repo.facility_id,
                frozenset({"sync.read"}),
                ORIGIN + timedelta(days=1),
            ),
            ORIGIN + timedelta(seconds=4),
        ).state
        == "SYNCHRONIZED"
        and service.pending_count() == 0
    )
    assert (
        service.snapshot(
            Principal(
                "viewer",
                repo.org_id,
                repo.facility_id,
                frozenset({"sync.read"}),
                ORIGIN + timedelta(days=1),
            ),
            ORIGIN + timedelta(seconds=4),
        ).pending_count
        == 0
    )
    edge_id = repo.edge_id
    repo.close()
    reopened = Repository(path)
    assert reopened.edge_id == edge_id
    assert (
        reopened.db.execute(
            "SELECT acknowledged_sequence FROM sync_streams WHERE stream='telemetry'"
        ).fetchone()[0]
        == 10
    )
    with psycopg.connect(postgres) as conn:
        assert (
            cloud_count(
                conn,
                "SELECT COUNT(*) FROM sync_events WHERE edge_id=%s AND stream='telemetry'",
                edge_id,
            )
            == 10
        )
    reopened.close()


def test_dispatch_and_finance_events_replay_without_actions(postgres: str, tmp_path: Path) -> None:
    path = tmp_path / "operational.db"
    repo, optimization, request = setup(path)
    run = optimization.run(request, now=ORIGIN)
    dispatch = DispatchService(repo, ForecastService(repo))
    principal = Principal(
        "human", repo.org_id, repo.facility_id, SIMULATION_PERMISSIONS, ORIGIN + timedelta(hours=1)
    )
    command = dispatch.request(
        ApprovalRequest(request_id=uuid4(), run_id=run.id), principal, now=ORIGIN
    )
    FinanceService(repo).tariff(tariff_write(), principal, ORIGIN)
    cloud = CloudRepository(postgres)
    token = enroll(cloud, repo)
    service = SyncService(repo, token=token, transport=DirectTransport(cloud))
    for stream in ("dispatch", "finance"):
        batch = service.pending_batch(stream)
        assert batch
        first = cloud.apply(batch, token)
        again = cloud.apply(batch, token)
        assert again.accepted == 0 and again.replayed == len(batch.entries)
        service.acknowledge(batch, first, ORIGIN)
    assert dispatch.load(command.id).state == "PENDING_APPROVAL"
    assert repo.db.execute("SELECT COUNT(*) FROM dispatch_commands").fetchone()[0] == 1
    assert repo.db.execute("SELECT COUNT(*) FROM finance_tariffs").fetchone()[0] == 1
    with psycopg.connect(postgres) as conn:
        assert (
            cloud_count(
                conn,
                "SELECT COUNT(*) FROM sync_events WHERE edge_id=%s AND stream='dispatch'",
                repo.edge_id,
            )
            == 1
        )
        assert (
            cloud_count(
                conn,
                "SELECT COUNT(*) FROM sync_events WHERE edge_id=%s AND stream='finance'",
                repo.edge_id,
            )
            == 1
        )
    repo.close()


def test_conflicted_dispatch_is_quarantined_while_finance_uploads(
    postgres: str, tmp_path: Path
) -> None:
    repo, optimization, request = setup(tmp_path / "conflicted.db")
    run = optimization.run(request, now=ORIGIN)
    dispatch = DispatchService(repo, ForecastService(repo))
    principal = Principal(
        "human", repo.org_id, repo.facility_id, SIMULATION_PERMISSIONS, ORIGIN + timedelta(hours=1)
    )
    command = dispatch.request(
        ApprovalRequest(request_id=uuid4(), run_id=run.id), principal, now=ORIGIN
    )
    FinanceService(repo).tariff(tariff_write(), principal, ORIGIN)
    cloud = CloudRepository(postgres)
    token = enroll(cloud, repo)
    service = SyncService(repo, token=token, transport=DirectTransport(cloud))
    batch = service.pending_batch("dispatch")
    assert batch
    changed = batch.entries[0].body | {"reason": "cloud-side divergence"}
    cloud.apply(
        batch.model_copy(
            update={
                "entries": [
                    batch.entries[0].model_copy(update={"body": changed, "digest": digest(changed)})
                ]
            }
        ),
        token,
    )
    service.tick(ORIGIN)
    assert service.state == "CONFLICT"
    assert (
        repo.db.execute(
            "SELECT conflict_code FROM sync_streams WHERE stream='dispatch'"
        ).fetchone()[0]
        == "REPLAY_CONFLICT"
    )
    assert (
        repo.db.execute("SELECT COUNT(*) FROM finance_outbox WHERE acknowledged=0").fetchone()[0]
        == 0
    )
    assert dispatch.load(command.id).state == "PENDING_APPROVAL"
    with psycopg.connect(postgres) as conn:
        assert (
            cloud_count(
                conn,
                "SELECT COUNT(*) FROM sync_events WHERE edge_id=%s AND stream='dispatch'",
                repo.edge_id,
            )
            == 1
        )
        assert (
            cloud_count(
                conn,
                "SELECT COUNT(*) FROM sync_events WHERE edge_id=%s AND stream='finance'",
                repo.edge_id,
            )
            == 1
        )
    repo.close()
