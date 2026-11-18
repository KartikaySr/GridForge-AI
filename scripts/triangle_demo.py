"""Launch one isolated synthetic factory across desktop, web and mobile APIs."""

import argparse
import json
import os
import secrets
import signal
import sqlite3
import subprocess
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import uvicorn

from cloud.portal import create_portal_app
from scripts.demo_cloud import local_postgres, receiver
from services.alerting.service import IncidentService
from services.demonstration.contracts import DemoStep
from services.demonstration.service import ACTIONS, DemoService
from services.dispatch.permissions import SIMULATION_PERMISSIONS, Principal
from services.portal.contracts import FieldReportWrite, PortalLogin
from services.portal.reports import receive_report
from services.portal.service import PortalService
from services.reporting.contracts import ProductionWrite
from services.reporting.service import ReportingService
from services.security.contracts import UserWrite
from services.security.identity import IdentityService
from services.sync.service import HttpCloudTransport


def prepare(demo: DemoService, dsn: str, directory: Path) -> None:
    actor = Principal(
        "triangle-demo",
        demo.repo.org_id,
        demo.repo.facility_id,
        SIMULATION_PERMISSIONS,
        datetime.now(UTC) + timedelta(hours=8),
    )
    for action in ACTIONS:
        demo.step(DemoStep(request_id=uuid4(), action=action), actor)
    # Fill the historical gap so real-time startup has five complete recent minute bins.
    demo.scenario = "normal"
    demo.advance(max(0, int((datetime.now(UTC) - demo.now).total_seconds()) - 1))
    demo.drain(actor)
    IncidentService(demo.repo).tick()
    reporting = ReportingService(demo.repo)
    for offset in (130, 70):
        start = demo.now - timedelta(seconds=offset)
        report = reporting.create(
            ProductionWrite(
                request_id=uuid4(),
                product="Synthetic demonstration batch",
                starts_at=start,
                ends_at=start + timedelta(seconds=60),
                asset_ids=["SIM-1", "SIM-2", "SIM-3", "SIM-4", "SIM-5"],
                good_tonnes=Decimal("1"),
                rejected_tonnes=Decimal("0.01"),
                note="SIMULATION: declared output for the demonstration batch.",
            ),
            actor,
            datetime.now(UTC),
        )
        if report.status != "COMPLETE":
            raise RuntimeError("Simulation production report lacks complete telemetry")
    password = secrets.token_urlsafe(24)
    IdentityService(demo.repo, demo.audit, uuid4()).create(
        UserWrite(username="prototype", password=password, role="ORG_ADMIN")
    )
    portal = PortalService(dsn)
    portal.migrate()
    # Unique cloud username allows repeated demos in a configured hosted database.
    username = "demo-" + demo.repo.edge_id.hex[:12]
    login = PortalLogin(username=username, password=password)
    portal.provision(login, demo.repo.org_id, demo.repo.facility_id)
    mobile = PortalService(dsn, client="mobile")
    token, user = mobile.login(login)
    receive_report(
        dsn,
        user,
        FieldReportWrite(
            request_id=uuid4(),
            edge_id=demo.repo.edge_id,
            text="SIMULATED inspection: compressor checked before the peak-demand rehearsal.",
        ),
    )
    mobile.logout(token)
    with sqlite3.connect(directory / "edge.db") as destination:
        demo.repo.db.backup(destination)
    descriptor = os.open(directory / "login.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as target:
        json.dump(
            {
                "mode": "SIMULATION",
                "desktop_username": "prototype",
                "portal_username": username,
                "password": password,
                "edge_id": str(demo.repo.edge_id),
                "facility_id": str(demo.repo.facility_id),
            },
            target,
            indent=2,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve-simulation", action="store_true")
    parser.add_argument(
        "--use-configured-cloud",
        action="store_true",
        help="Use GRIDFORGE_CLOUD_DATABASE_URL for a dedicated synthetic facility",
    )
    args = parser.parse_args()
    if not args.approve_simulation:
        parser.error("--approve-simulation is required for seeded simulated dispatch")
    identifier = uuid4()
    directory = Path(".local") / f"triangle-{identifier}"
    directory.mkdir(parents=True, mode=0o700)
    database = (
        nullcontext(os.environ["GRIDFORGE_CLOUD_DATABASE_URL"])
        if args.use_configured_cloud
        else local_postgres()
    )
    demo = DemoService()
    children: list[subprocess.Popen[bytes]] = []
    try:
        with database as dsn, receiver(demo, dsn):
            prepare(demo, dsn, directory)
            assert demo.network and isinstance(demo.network.transport, HttpCloudTransport)
            environment = os.environ | {
                "GRIDFORGE_DEMO_ID": str(identifier),
                "GRIDFORGE_CLOUD_URL": demo.network.transport.url,
                "GRIDFORGE_EDGE_TOKEN": demo.sync.token or "",
            }
            children.append(
                subprocess.Popen(["npm", "run", "web"], env=environment, start_new_session=True)
            )
            children.append(
                subprocess.Popen(
                    ["npm", "run", "desktop:native"], env=environment, start_new_session=True
                )
            )
            print(
                f"SIMULATION: shared factory prepared. Private login: {directory}/login.json",
                flush=True,
            )
            print(
                "Web: http://127.0.0.1:5174. Desktop produces 1 Hz telemetry after startup. "
                "Mobile uses the same portal through a reachable HTTPS origin.",
                flush=True,
            )
            uvicorn.run(
                create_portal_app(dsn, "http://127.0.0.1:5174", secure=False),
                host="127.0.0.1",
                port=8082,
                access_log=False,
                log_level="warning",
            )
    finally:
        for child in children:
            if child.poll() is None:
                if os.name == "posix":
                    os.killpg(child.pid, signal.SIGTERM)
                else:
                    child.terminate()
        for child in children:
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        demo.close()


if __name__ == "__main__":
    main()
