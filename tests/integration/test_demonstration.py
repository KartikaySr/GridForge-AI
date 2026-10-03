from uuid import uuid4

import psycopg

from scripts.demo_cloud import receiver
from services.demonstration.contracts import DemoStep
from services.demonstration.service import ACTIONS, DemoService
from tests.integration.test_sync_postgres import postgres  # noqa: F401
from tests.unit.test_demonstration import actor


def test_full_canonical_scenario_and_real_http_reconciliation(postgres: str) -> None:  # noqa: F811
    demo = DemoService()
    principal = actor(demo)
    try:
        with receiver(demo, postgres):
            for action in ACTIONS:
                result = demo.step(DemoStep(request_id=uuid4(), action=action), principal)
                if action == "disconnect":
                    assert result.sync.state == "OFFLINE"
                    assert result.sync.pending_count >= 50
            assert result.next_action is None
            assert result.sync.state == "SYNCHRONIZED" and result.sync.pending_count == 0
            assert len(result.steps) == 9 and result.audit_integrity_ok
            with psycopg.connect(postgres) as db:
                # Read-only reconciliation proof; setup and mutations use actual domain services.
                total = db.execute(
                    "SELECT COUNT(*) FROM sync_events WHERE edge_id=%s", (demo.repo.edge_id,)
                ).fetchone()
                assert total and total[0] == sum(s.local_last_sequence for s in result.sync.streams)
            before = result.sync
            demo.drain(principal)
            after = demo.sync.snapshot(principal, demo.now)
            assert [s.acknowledged_sequence for s in before.streams] == [
                s.acknowledged_sequence for s in after.streams
            ]
    finally:
        demo.close()
