from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient

from cloud.portal import create_portal_app
from tests.integration.test_portal import ORIGIN, fixture
from tests.integration.test_sync_postgres import postgres  # noqa: F401


def test_mobile_scope_sessions_and_idempotent_reports(postgres: str) -> None:  # noqa: F811
    service, edge, username = fixture(postgres)
    app = create_portal_app(postgres, ORIGIN, secure=False)
    with TestClient(app) as client:
        credentials = {"username": username, "password": "portal-test-password"}
        assert (
            client.post("/api/v1/login", json=credentials, headers={"Origin": ORIGIN}).status_code
            == 200
        )
        assert client.get("/api/v1/mobile/me").status_code == 401
        assert (
            client.post(
                "/api/v1/mobile/login", json=credentials, headers={"Origin": ORIGIN}
            ).status_code
            == 403
        )
        response = client.post("/api/v1/mobile/login", json=credentials)
        assert response.status_code == 200
        headers = {"Authorization": "Bearer " + response.json()["token"]}
        assert client.get("/api/v1/portfolio").status_code == 200  # mobile preserves web session
        assert client.get("/api/v1/mobile/me", headers=headers).status_code == 200
        assert client.get("/api/v1/mobile/portfolio", headers=headers).json()["facilities"][0][
            "edge_id"
        ] == str(edge.edge_id)
        report = {
            "request_id": str(uuid4()),
            "edge_id": str(edge.edge_id),
            "text": "Synthetic pump observation",
        }
        first = client.post("/api/v1/mobile/reports", json=report, headers=headers)
        assert first.status_code == 200
        assert (
            client.post("/api/v1/mobile/reports", json=report, headers=headers).json()
            == first.json()
        )
        assert (
            client.post(
                "/api/v1/mobile/reports", json={**report, "text": "Changed"}, headers=headers
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/api/v1/mobile/reports", json={**report, "edge_id": str(uuid4())}, headers=headers
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/v1/mobile/reports", json={**report, "text": "   "}, headers=headers
            ).status_code
            == 422
        )
        assert (
            client.post("/api/v1/mobile/reports", content="x" * 16385, headers=headers).status_code
            == 413
        )
        with psycopg.connect(postgres) as conn:
            conn.execute(
                "DELETE FROM portal_memberships WHERE user_id=%s",
                (response.json()["identity"]["id"],),
            )
        assert (
            client.post("/api/v1/mobile/reports", json=report, headers=headers).status_code == 404
        )
        assert client.post("/api/v1/mobile/logout", json={}, headers=headers).status_code == 200
        assert client.get("/api/v1/mobile/me", headers=headers).status_code == 401
        assert client.get("/api/v1/portfolio").status_code == 200
    edge.close()
