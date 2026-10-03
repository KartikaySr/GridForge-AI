"""Canonical, accelerated SIMULATION acceptance; actual domain services and PostgreSQL HTTP."""

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from scripts.demo_cloud import local_postgres, receiver
from services.demonstration.contracts import DemoStep
from services.demonstration.service import ACTIONS, DemoService
from services.dispatch.permissions import SIMULATION_PERMISSIONS, Principal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--approve-simulation",
        action="store_true",
        help="Explicitly authorize simulated approval in this disposable acceptance run.",
    )
    parser.add_argument("--output", type=Path, default=Path(".local/phase11-demo.json"))
    args = parser.parse_args()
    if not args.approve_simulation:
        parser.error("Explicit --approve-simulation is required; no equipment is controlled.")
    demo = DemoService()
    actor = Principal(
        "authorized-simulation-acceptance",
        demo.repo.org_id,
        demo.repo.facility_id,
        SIMULATION_PERMISSIONS,
        datetime.now(UTC) + timedelta(hours=8),
    )
    try:
        with local_postgres() as dsn, receiver(demo, dsn):
            for action in ACTIONS:
                result = demo.step(DemoStep(request_id=uuid4(), action=action), actor)
                print(f"{action}: {result.steps[-1].detail}", flush=True)
            assert result.next_action is None and result.sync.pending_count == 0
            assert result.audit_integrity_ok and result.verification
            assert (
                result.verification.net_energy_value is not None
                and result.verification.net_energy_value > 0
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(result.model_dump_json(indent=2) + "\n")
            print(f"PASS: complete isolated simulation; evidence saved to {args.output}")
    finally:
        demo.close()


if __name__ == "__main__":
    main()
