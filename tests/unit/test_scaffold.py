"""Scaffold checks only: these do not certify operational readiness."""

from collections.abc import Iterator

import pytest
from app.core.config import load_settings
from app.main import app, latest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> Iterator[TestClient]:
    latest.clear()
    with TestClient(app) as test_client:
        yield test_client
    latest.clear()


def test_liveness_explicitly_identifies_simulation(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["mode"] == "SIMULATION"
    assert response.json()["check"] == "liveness"


def test_telemetry_ingestion_updates_load_without_claiming_verification(client: TestClient) -> None:
    point = {
        "timestamp": "2026-01-01T00:00:00Z",
        "asset_id": "CH-01",
        "voltage": 415,
        "current": 10,
        "active_power_kw": 123.5,
        "vibration": 1.2,
    }
    response = client.post("/api/v1/telemetry", json=point)
    assert response.status_code == 200
    metrics = client.get("/api/v1/dashboard/metrics").json()
    assert metrics["currentLoadKw"] == 123.5
    assert metrics["source"] == "simulation-scaffold"
    assert metrics["mode"] == "SIMULATION"
    point["active_power_kw"] = -1
    assert client.post("/api/v1/telemetry", json=point).status_code == 422
    assert client.get("/api/v1/dashboard/metrics").json()["currentLoadKw"] == 123.5


def test_malformed_payload_does_not_change_state(client: TestClient) -> None:
    assert client.post("/api/v1/telemetry", json={"asset_id": "CH-01"}).status_code == 422
    assert not latest


def test_static_proposal_declares_its_source(client: TestClient) -> None:
    proposal = client.get("/api/v1/optimization/current").json()
    assert proposal["source"] == "static-fixture"
    assert proposal["mode"] == "SIMULATION"
    assert proposal["status"] == "proposed"


@pytest.mark.parametrize("mode", ["PRODUCTION", "LIVE", "", "simulation"])
def test_configuration_rejects_non_simulation_modes(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    monkeypatch.setenv("GRIDFORGE_MODE", mode)
    with pytest.raises(ValueError, match="Only SIMULATION"):
        load_settings()


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://example.com",
        "http://localhost.evil:5173",
        "http://user@localhost:5173",
        "http://localhost:5173/path",
        "",
    ],
)
def test_configuration_rejects_non_loopback_origins(
    monkeypatch: pytest.MonkeyPatch, origin: str
) -> None:
    monkeypatch.setenv("GRIDFORGE_CORS_ORIGINS", origin)
    with pytest.raises(ValueError):
        load_settings()


def test_default_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GRIDFORGE_MODE", raising=False)
    monkeypatch.delenv("GRIDFORGE_CORS_ORIGINS", raising=False)
    settings = load_settings()
    assert settings.mode == "SIMULATION"
    assert "http://127.0.0.1:5173" in settings.cors_origins


def test_cors_does_not_allow_external_origin(client: TestClient) -> None:
    response = client.options(
        "/api/v1/telemetry",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
