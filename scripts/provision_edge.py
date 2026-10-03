"""Administrator-run enrollment. Creates a 0600 token file, never a public API route."""

import argparse
import os
import secrets
from pathlib import Path

from cloud.repository import CloudRepository
from edge.storage.repository import Repository


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edge-db", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ["GRIDFORGE_CLOUD_DATABASE_URL"]
    token = secrets.token_hex(32)
    descriptor = os.open(args.token_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "w") as file:
            file.write(token + "\n")
        edge = Repository(args.edge_db)
        try:
            CloudRepository(dsn).enroll(edge.edge_id, edge.org_id, edge.facility_id, token)
            print(f"Enrolled edge {edge.edge_id} for facility {edge.facility_id}")
            print(f"Token file: {args.token_file} (mode 0600)")
        finally:
            edge.close()
    except Exception:
        # Preserve the token file so a failed enrollment can be diagnosed without
        # accidentally creating another secret for the same edge.
        raise


if __name__ == "__main__":
    main()
