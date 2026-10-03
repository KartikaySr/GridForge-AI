import secrets
from uuid import uuid4

from fastapi.testclient import TestClient

from edge.runtime.state import RuntimeState
from tests.support import create_app


def test_all_runtime_routes_require_private_session() -> None:
    token = secrets.token_hex(32)
    with TestClient(create_app(token, uuid4())) as client:
        for path in ("/api/v1/system/health", "/api/v1/system/diagnostics", "/openapi.json"):
            denied = client.get(path)
            assert denied.status_code == 401
            assert denied.json()["code"] == "LOCAL_AUTH_REQUIRED"
            assert denied.headers["cache-control"] == "no-store"
        assert (
            client.get(
                "/api/v1/system/health", headers={"Authorization": "Bearer wrong"}
            ).status_code
            == 401
        )
        allowed = client.get("/api/v1/system/health", headers={"Authorization": f"Bearer {token}"})
        assert allowed.status_code == 200
        assert allowed.json()["operational_ready"] is False
        assert allowed.json()["readiness_scope"] == "telemetry"
        assert allowed.json()["cloud_state"] == "NOT_CONFIGURED"
        assert allowed.json()["facility_id"] is not None


def test_browser_origin_is_denied_even_with_a_valid_token() -> None:
    token = secrets.token_hex(32)
    with TestClient(create_app(token, uuid4())) as client:
        response = client.get(
            "/api/v1/system/health",
            headers={
                "Authorization": f"Bearer {token}",
                "Origin": "http://localhost:5173",
            },
        )
        assert response.status_code == 401
        assert "access-control-allow-origin" not in response.headers


def test_credentials_do_not_survive_a_new_runtime_session() -> None:
    old_token, token = secrets.token_hex(32), secrets.token_hex(32)
    with TestClient(create_app(token, uuid4())) as client:
        assert (
            client.get(
                "/api/v1/system/health", headers={"Authorization": f"Bearer {old_token}"}
            ).status_code
            == 401
        )


def test_diagnostics_never_reflect_request_secrets_or_paths() -> None:
    token = secrets.token_hex(32)
    with TestClient(create_app(token, uuid4())) as client:
        client.get("/private-secret?key=sensitive", headers={"Authorization": "Bearer bad-secret"})
        response = client.get(
            "/api/v1/system/diagnostics", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        for secret in (token, "bad-secret", "private-secret", "sensitive", "Bearer"):
            assert secret not in response.text
        assert response.json()["logs"][-1]["event"] == "request.denied"


def test_logs_are_bounded_with_explicit_discard_count() -> None:
    state = RuntimeState(uuid4())
    for _ in range(120):
        state.record("request.completed")
    diagnostics = state.diagnostics()
    assert len(diagnostics.logs) == 100
    assert diagnostics.discarded_log_count == 21
