"""Provision an existing facility's read-only browser user through a private admin terminal."""

import argparse
import getpass
import os
from uuid import UUID

from cloud.repository import CloudRepository
from services.portal.contracts import PortalLogin
from services.portal.service import PortalService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--org-id", type=UUID, required=True)
    parser.add_argument("--facility-id", type=UUID, required=True)
    args = parser.parse_args()
    dsn = os.environ["GRIDFORGE_CLOUD_DATABASE_URL"]
    CloudRepository(dsn).migrate()
    service = PortalService(dsn)
    service.migrate()
    password = getpass.getpass("New portal password (12–128 characters): ")
    if password != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords do not match")
    service.provision(
        PortalLogin(username=args.username, password=password), args.org_id, args.facility_id
    )
    print("Read-only portal user provisioned. Password was not logged.")


if __name__ == "__main__":
    main()
