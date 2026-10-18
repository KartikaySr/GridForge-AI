"""Temporary PostgreSQL-backed portal populated through the actual domain/sync chain."""

import argparse
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import uvicorn

from cloud.portal import create_portal_app
from scripts.demo_cloud import local_postgres, receiver
from services.demonstration.contracts import DemoStep
from services.demonstration.service import ACTIONS, DemoService
from services.dispatch.permissions import SIMULATION_PERMISSIONS, Principal
from services.portal.contracts import PortalLogin
from services.portal.service import PortalService


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve-simulation", action="store_true")
    args = parser.parse_args()
    if not args.approve_simulation:
        parser.error(
            "--approve-simulation is required for the isolated simulated dispatch rehearsal"
        )
    demo = DemoService()
    actor = Principal(
        "web-demo",
        demo.repo.org_id,
        demo.repo.facility_id,
        SIMULATION_PERMISSIONS,
        datetime.now(UTC) + timedelta(hours=8),
    )
    credentials = Path(".local/web-demo-login.json")
    credentials_created = False
    try:
        with local_postgres() as dsn, receiver(demo, dsn):
            for action in ACTIONS:
                demo.step(DemoStep(request_id=uuid4(), action=action), actor)
            app = create_portal_app(dsn, "http://127.0.0.1:5174", secure=False)
            password = secrets.token_urlsafe(24)
            PortalService(dsn).provision(
                PortalLogin(username="prototype", password=password),
                demo.repo.org_id,
                demo.repo.facility_id,
            )
            credentials.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor = os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            credentials_created = True
            with os.fdopen(descriptor, "w") as target:
                json.dump(
                    {
                        "username": "prototype",
                        "password": password,
                        "web_url": "http://127.0.0.1:5174",
                        "mode": "TEMPORARY_SIMULATION",
                    },
                    target,
                )
            print(
                "Portal ready on 127.0.0.1:8082. Run npm run web. "
                "Private login: .local/web-demo-login.json",
                flush=True,
            )
            uvicorn.run(app, host="127.0.0.1", port=8082, access_log=False, log_level="warning")
    finally:
        if credentials_created:
            credentials.unlink(missing_ok=True)
        demo.close()


if __name__ == "__main__":
    main()
