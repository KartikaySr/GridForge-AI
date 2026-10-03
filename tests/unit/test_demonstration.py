from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from edge.runtime.app import create_app
from edge.storage.repository import Rejected
from services.demonstration.contracts import DemoStep
from services.demonstration.service import ACTIONS, DemoService
from services.dispatch.permissions import SIMULATION_PERMISSIONS, PermissionDenied, Principal


def actor(demo: DemoService) -> Principal:
    return Principal(
        "demo-operator",
        demo.repo.org_id,
        demo.repo.facility_id,
        SIMULATION_PERMISSIONS,
        datetime.now(UTC) + timedelta(hours=1),
    )


def test_isolated_domain_chain_human_gate_and_actual_verification() -> None:
    demo = DemoService()
    principal = actor(demo)
    try:
        with pytest.raises(Rejected, match="OUT_OF_ORDER"):
            demo.step(DemoStep(request_id=uuid4(), action="approve"), principal)
        for action in ACTIONS[:4]:
            write = DemoStep(request_id=uuid4(), action=action)
            result = demo.step(write, principal)
            rows = result.telemetry_rows
            assert demo.step(write, principal) == result
            assert demo.repo.state()[2]["accepted"] == rows
        assert result.command and result.command.state == "PENDING_APPROVAL"
        assert result.run and result.run.proposal
        critical = next(c for c in result.run.candidates if c.asset_id == "SIM-5")
        assert not critical.eligible and critical.selected_kw == 0
        assert not demo.dispatch.adapter.reductions(demo.now)
        denied = Principal(
            "limited",
            principal.org_id,
            principal.facility_id,
            frozenset({"system.configure"}),
            principal.expires_at,
        )
        with pytest.raises(PermissionDenied):
            demo.step(DemoStep(request_id=uuid4(), action="approve"), denied)
        assert demo.dispatch.load(result.command.id).state == "PENDING_APPROVAL"
        for action in ACTIONS[4:7]:
            result = demo.step(DemoStep(request_id=uuid4(), action=action), principal)
        assert result.command and result.command.state == "COMPLETED"
        assert result.verification and result.verification.status == "VERIFIED"
        assert result.verification.execution and result.verification.execution.valid_slots == 60
        assert result.verification.rebound and result.verification.rebound.valid_slots == 60
        assert result.verification.net_energy_value and result.verification.net_energy_value > 0
        assert result.explanation and result.explanation.evidence
        assert result.audit_integrity_ok
        with pytest.raises(Rejected, match="NOT_CONFIGURED"):
            demo.step(DemoStep(request_id=uuid4(), action="disconnect"), principal)
        assert len(demo.steps) == 7
    finally:
        demo.close()


def test_api_requires_identity_and_never_modifies_main_facility() -> None:
    app = create_app("a" * 64, uuid4(), simulate=False)
    with TestClient(app, headers={"Authorization": "Bearer " + "a" * 64}) as client:
        assert client.get("/api/v1/demo").status_code == 403
        assert (
            client.post(
                "/api/v1/identity/bootstrap",
                json={"username": "demo-admin", "password": "only-test-password-2026"},
            ).status_code
            == 200
        )
        original = app.state.telemetry.repo.registry.records()
        demo = client.get("/api/v1/demo").json()
        assert demo["facility_id"] != str(app.state.telemetry.repo.facility_id)
        assert (
            client.post(
                "/api/v1/demo", json={"request_id": str(uuid4()), "action": "normal"}
            ).status_code
            == 200
        )
        assert app.state.telemetry.repo.registry.records() == original
        assert app.state.telemetry.repo.state()[2]["accepted"] == 0
        assert client.post("/api/v1/identity/logout").status_code == 200
        assert client.get("/api/v1/demo").status_code == 403
