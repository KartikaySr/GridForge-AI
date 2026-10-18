import hashlib
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from cloud.portal import COOKIE, create_portal_app
from cloud.repository import CloudRepository
from edge.storage.repository import Repository
from services.portal.contracts import PortalLogin
from services.portal.service import PortalDenied, PortalService
from services.sync.codec import digest
from services.sync.contracts import SyncBatch, SyncEntry
from tests.integration.test_sync_postgres import postgres  # noqa: F401, F811
from tests.unit.test_telemetry import NOW, batch

ORIGIN = "http://127.0.0.1:5174"


def fixture(dsn: str) -> tuple[PortalService, Repository, str]:
    cloud = CloudRepository(dsn)
    cloud.migrate()
    portal = PortalService(dsn)
    portal.migrate()
    edge = Repository(None)
    cloud.enroll(edge.edge_id, edge.org_id, edge.facility_id, "a" * 64)
    edge.ingest(batch(edge), NOW)
    entries = [
        SyncEntry(
            sequence=i + 1,
            event_id=e.event_id,
            digest=digest(e.model_dump(mode="json")),
            body=e.model_dump(mode="json"),
        )
        for i, e in enumerate(edge.events())
    ]
    cloud.apply(SyncBatch(edge_id=edge.edge_id, stream="telemetry", entries=entries), "a" * 64)
    username = "reader-" + uuid4().hex[:10]
    portal.provision(
        PortalLogin(username=username, password="portal-test-password"),
        edge.org_id,
        edge.facility_id,
    )
    return portal, edge, username


def test_scope_rls_history_and_session_revocation(postgres: str) -> None:  # noqa: F811
    service, edge, username = fixture(postgres)
    cloud = CloudRepository(postgres)
    other = Repository(None)
    cloud.enroll(other.edge_id, other.org_id, other.facility_id, "b" * 64)
    token, user = service.login(PortalLogin(username=username, password="portal-test-password"))
    assert [f.edge_id for f in service.portfolio(user).facilities] == [edge.edge_id]
    history = service.history(user, edge.edge_id, "telemetry", 2**63 - 1)
    assert len(history.events) == 5 and history.events[0].sequence == 5
    assert service.history(user, edge.edge_id, "telemetry", 3).events[0].sequence == 2
    with pytest.raises(PortalDenied):
        service.history(user, other.edge_id, "telemetry", 2**63 - 1)
    with psycopg.connect(postgres) as conn:
        service.restrict(conn, user)
        assert conn.execute(
            "SELECT count(*) FROM sync_edges WHERE edge_id=%s", (other.edge_id,)
        ).fetchone() == (0,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM sync_events")
    with psycopg.connect(postgres) as conn:
        conn.execute("DELETE FROM portal_memberships WHERE user_id=%s", (user.id,))
    assert service.portfolio(user).facilities == []
    assert service.identity(token).id == user.id
    service.logout(token)
    with pytest.raises(PortalDenied):
        service.identity(token)
    with pytest.raises(PortalDenied):
        service.identity("a" * 64)
    edge.close()
    other.close()


def test_browser_origin_cookies_expiry_and_edge_token_rejection(postgres: str) -> None:  # noqa: F811
    service, edge, username = fixture(postgres)
    app = create_portal_app(postgres, ORIGIN, secure=False)
    with TestClient(app) as client:
        assert (
            client.get(
                "/api/v1/portfolio",
                headers={"Authorization": "Bearer " + "a" * 64, "X-Edge-ID": str(edge.edge_id)},
            ).status_code
            == 401
        )
        login = {"username": username, "password": "portal-test-password"}
        assert client.post("/api/v1/login", json=login).status_code == 403
        assert (
            client.post(
                "/api/v1/login", headers={"Origin": "https://evil.example"}, json=login
            ).status_code
            == 403
        )
        response = client.post("/api/v1/login", headers={"Origin": ORIGIN}, json=login)
        assert response.status_code == 200, response.text
        assert (
            "HttpOnly" in response.headers["set-cookie"]
            and "SameSite=strict" in response.headers["set-cookie"]
        )
        assert client.get("/api/v1/portfolio").status_code == 200
        assert client.get(f"/api/v1/facilities/{edge.edge_id}/events?before=-1").status_code == 422
        assert (
            client.post("/api/v1/dispatch", headers={"Origin": ORIGIN}, json={}).status_code == 404
        )
        token = client.cookies.get(COOKIE)
        with psycopg.connect(postgres) as conn:
            conn.execute(
                "UPDATE portal_sessions SET expires_at=now()-interval '1 second' "
                "WHERE token_hash=%s",
                (hashlib.sha256(str(token).encode()).hexdigest(),),
            )
        assert client.get("/api/v1/me").status_code == 401
    edge.close()


def test_cookie_transport_configuration() -> None:
    with pytest.raises(ValueError):
        create_portal_app("", "http://production.example", secure=False, migrate=False)
    with pytest.raises(ValueError):
        create_portal_app("", ORIGIN, migrate=False)
