"""Cross-domain SIMULATION regression through approval, verification, AI and cloud replay."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from cloud.repository import CloudRepository
from services.ai.contracts import AskRequest
from services.ai.service import AIService
from services.finance.contracts import VerificationRequest
from services.finance.service import FinanceService
from services.security.audit import AuditService
from services.sync.service import SyncService
from tests.integration.test_sync_postgres import DirectTransport, enroll, postgres  # noqa: F401
from tests.unit.test_finance import completed_command, replace_measurements, tariff_write
from tests.unit.test_forecasting import ORIGIN


def test_simulation_pipeline_to_cloud_with_duplicate_delivery(postgres: str) -> None:  # noqa: F811
    repo, _, actor, command = completed_command()
    replace_measurements(repo, 90, 102)
    finance = FinanceService(repo)
    tariff = finance.tariff(tariff_write(), actor, ORIGIN)
    finance.start(
        VerificationRequest(request_id=uuid4(), command_id=command.id, tariff_id=tariff.id),
        actor,
        ORIGIN + timedelta(seconds=304),
    )
    finance.tick(ORIGIN + timedelta(seconds=607))
    snapshot = finance.snapshot(actor, ORIGIN + timedelta(seconds=607))
    assert any(entry.status == "VERIFIED" for entry in snapshot.ledger)
    actor = replace(actor, expires_at=datetime.now(UTC) + timedelta(hours=1))
    answer = AIService(repo).ask(
        AskRequest(
            request_id=uuid4(),
            question="What savings are recorded?",
            intent="ANALYTICS",
            sql="SELECT entry_id, status, currency, amount FROM ai_savings",
        ),
        actor,
    )
    assert answer.advisory_only
    assert answer.status == "ANSWERED"
    AuditService(repo).record("pipeline.verified", "success", actor.actor, command.id)
    cloud = CloudRepository(postgres)
    cloud.migrate()
    token = enroll(cloud, repo)
    transport = DirectTransport(cloud)
    transport.lose_one_ack = True
    sync = SyncService(repo, transport=transport, token=token)
    for _ in range(100):
        sync.tick(ORIGIN + timedelta(seconds=609 + _))
        if sync.snapshot(actor).pending_count == 0:
            break
    assert sync.snapshot(actor).pending_count == 0
    assert AuditService(repo).verify()
    repo.close()
