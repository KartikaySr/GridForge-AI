import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from edge.runtime.app import create_app
from edge.storage.repository import Repository
from services.dispatch.permissions import Principal
from services.security.audit import AuditService
from services.security.contracts import Login, UserChange, UserWrite
from services.security.identity import IdentityRejected, IdentityService
from services.security.policy import ROLES

TOKEN = "a" * 64
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def test_bootstrap_login_roles_logout_restart_and_redaction(tmp_path: Path) -> None:
    path = tmp_path / "edge.db"
    credentials = {"username": "administrator", "password": secrets.token_hex(16)}
    with TestClient(create_app(TOKEN, uuid4(), path, simulate=False), headers=HEADERS) as client:
        assert client.get("/api/v1/registry").status_code == 403
        assert client.get("/api/v1/identity").json()["setup_required"]
        status = client.post("/api/v1/identity/bootstrap", json=credentials)
        assert status.status_code == 200
        assert status.json()["authenticated"]
        assert client.post("/api/v1/identity/bootstrap", json=credentials).status_code == 403
        assert client.get("/api/v1/registry").status_code == 200
        viewer = dict(username="viewer", password=secrets.token_hex(16), role="VIEWER")
        assert client.post("/api/v1/identity/users", json=viewer).status_code == 200
        assert client.post("/api/v1/identity/users", json=viewer).status_code == 409
        assert (
            client.post(
                "/api/v1/identity/login", json={k: viewer[k] for k in ["username", "password"]}
            ).status_code
            == 200
        )
        assert client.get("/api/v1/registry").status_code == 200
        assert client.post("/api/v1/registry", json={"role": "SUPER_ADMIN"}).status_code == 403
        assert client.get("/api/v1/identity/users").status_code == 403
        assert client.get("/api/v1/system/authorize").status_code == 403
        assert client.get("/api/v1/system/bundle").status_code == 403
        assert client.post("/api/v1/identity/logout").status_code == 200
        assert client.get("/api/v1/telemetry/history").status_code == 403
        assert client.post("/api/v1/identity/login", json=credentials).status_code == 200
        audit = client.get("/api/v1/security/audit").json()
        assert audit["integrity_ok"] and audit["count"] >= 10
        bundle = client.get("/api/v1/system/bundle")
        assert bundle.status_code == 200
        assert credentials["password"] not in bundle.text
        assert "password_hash" not in bundle.text
        assert TOKEN not in bundle.text
        assert "X-Trace-ID" in bundle.headers
    with TestClient(create_app(TOKEN, uuid4(), path, simulate=False), headers=HEADERS) as client:
        assert not client.get("/api/v1/identity").json()["authenticated"]
        assert client.post("/api/v1/identity/login", json=credentials).status_code == 200


@pytest.mark.parametrize("role", list(ROLES))
def test_every_role_is_scoped_and_legacy_writes_are_guarded(tmp_path: Path, role: str) -> None:
    path = tmp_path / "roles.db"
    repo = Repository(path)
    org, facility = repo.org_id, repo.facility_id
    repo.close()
    actor = Principal(role, org, facility, ROLES[role], datetime.now(UTC) + timedelta(hours=1))
    with TestClient(
        create_app(TOKEN, uuid4(), path, principal=actor, simulate=False), headers=HEADERS
    ) as client:
        assert client.get("/api/v1/registry").status_code == 200
        for route, permission in [
            ("optimization/policies", "optimization.configure"),
            ("telemetry/batches", "telemetry.ingest"),
            ("simulator/scenario", "simulator.control"),
            ("identity/users", "user.manage"),
        ]:
            response = client.post("/api/v1/" + route, json={})
            assert response.status_code == (422 if permission in actor.permissions else 403)
    foreign = Principal(role, uuid4(), facility, ROLES[role], actor.expires_at)
    with TestClient(
        create_app(TOKEN, uuid4(), path, principal=foreign, simulate=False), headers=HEADERS
    ) as client:
        for route in [
            "registry",
            "telemetry/history",
            "intelligence",
            "optimization",
            "dispatch",
            "finance",
            "ai",
            "sync",
        ]:
            assert client.get("/api/v1/" + route).status_code == 403


def test_revocation_rate_limit_last_admin_and_hashing() -> None:
    repo = Repository(None)
    audit = AuditService(repo)
    service = IdentityService(repo, audit, uuid4())
    password = secrets.token_hex(16)
    user = service.create(UserWrite(username="admin", password=password, role="ORG_ADMIN"))
    service.login(Login(username="admin", password=password))
    actor = service.current()
    assert actor is not None
    with pytest.raises(IdentityRejected, match="LAST_ADMIN"):
        service.change(
            UserChange(user_id=user.id, role="VIEWER", enabled=True, expected_revision=1), actor
        )
    other = service.create(UserWrite(username="second", password=password, role="ORG_ADMIN"), actor)
    service.change(
        UserChange(user_id=user.id, role="VIEWER", enabled=True, expected_revision=1), actor
    )
    assert service.current() is None
    stored = repo.db.execute(
        "SELECT password_hash,salt FROM local_users ORDER BY username"
    ).fetchall()
    assert stored[0][0] != stored[1][0] and stored[0][1] != stored[1][1]
    assert other.enabled
    for _ in range(5):
        with pytest.raises(ValueError, match="LOGIN_FAILED"):
            service.login(Login(username="admin", password="wrong-password-123"))
    with pytest.raises(ValueError, match="RATE_LIMITED"):
        service.login(Login(username="second", password=password))
    repo.close()


def test_audit_immutability_and_corruption_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "audit.db"
    repo = Repository(path)
    audit = AuditService(repo)
    audit.record("test", "success")
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE"):
        repo.db.execute("DELETE FROM security_audit")
    repo.db.rollback()
    repo.db.execute("DROP TRIGGER audit_no_update")
    repo.db.execute("UPDATE security_audit SET digest='corrupted'")
    repo.db.commit()
    assert not audit.snapshot().integrity_ok
    with pytest.raises(ValueError, match="AUDIT_INTEGRITY_FAILURE"):
        audit.record("test", "success")
    repo.close()
    with TestClient(create_app(TOKEN, uuid4(), path, simulate=False), headers=HEADERS) as client:
        assert (
            client.post(
                "/api/v1/identity/bootstrap",
                json={"username": "admin", "password": secrets.token_hex(16)},
            ).status_code
            == 503
        )


def test_migration_checksum_mismatch_fails_startup(tmp_path: Path) -> None:
    path = tmp_path / "migrations.db"
    repo = Repository(path)
    repo.db.execute("UPDATE migration_history SET digest='tampered' WHERE version=1")
    repo.db.commit()
    repo.close()
    with pytest.raises(ValueError, match="MIGRATION_CHECKSUM_MISMATCH"):
        Repository(path)


def test_logout_remains_available_when_audit_fails_closed() -> None:
    app = create_app(TOKEN, uuid4(), simulate=False)
    with TestClient(app, headers=HEADERS) as client:
        assert (
            client.post(
                "/api/v1/identity/bootstrap",
                json={"username": "admin", "password": secrets.token_hex(16)},
            ).status_code
            == 200
        )
        app.state.audit.integrity_ok = False
        assert client.post("/api/v1/identity/logout").status_code == 200
        assert client.get("/api/v1/registry").status_code == 403
        assert app.state.identity.current() is None
