"""The deployed ASGI entrypoint must never migrate on import."""

import importlib
import sys
from unittest.mock import patch

from _pytest.monkeypatch import MonkeyPatch


def test_vercel_entrypoint_routes_without_database_access(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("GRIDFORGE_CLOUD_DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("GRIDFORGE_WEB_ORIGIN", "https://gridforge.example")
    sys.modules.pop("cloud.vercel_portal", None)
    with patch("psycopg.connect", side_effect=AssertionError("Cold start accessed database")):
        module = importlib.import_module("cloud.vercel_portal")
        paths = set(module.app.openapi()["paths"])
        assert {"/api/v1/login", "/api/v1/mobile/login", "/api/v1/mobile/reports"} <= paths
