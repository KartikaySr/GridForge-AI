"""Consistent SQLite backup and restore-to-new-file; never overwrite a running database."""

import argparse
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from services.security.audit import chain_hash


def validate(path: Path) -> dict[str, Any]:
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("BACKUP_INTEGRITY_FAILED")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("BACKUP_FOREIGN_KEY_FAILURE")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version not in range(1, 12):
            raise ValueError("UNSUPPORTED_BACKUP_SCHEMA")
        head = "0" * 64
        if version >= 9:
            for index, row in enumerate(
                db.execute(
                    "SELECT sequence,body,previous_hash,digest FROM security_audit "
                    "ORDER BY sequence"
                ),
                1,
            ):
                if row[0] != index or row[2] != head or chain_hash(head, row[1]) != row[3]:
                    raise ValueError("BACKUP_AUDIT_FAILURE")
                head = row[3]
        identity = db.execute("SELECT org_id,facility_id FROM identity").fetchone()
        return {
            "schema_version": version,
            "org_id": identity[0],
            "facility_id": identity[1],
            "audit_head": head,
        }


def backup(source: Path, destination: Path) -> dict[str, Any]:
    source = source.resolve(strict=True)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest = destination.with_suffix(destination.suffix + ".json")
    if manifest.exists():
        raise FileExistsError("BACKUP_MANIFEST_EXISTS")
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with (
            closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as origin,
            closing(sqlite3.connect(destination)) as target,
        ):
            origin.backup(target)
            target.execute("PRAGMA journal_mode=DELETE")
        result = validate(destination) | {
            "format": "gridforge-backup-v1",
            "created_at": datetime.now(UTC).isoformat(),
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        }
        with manifest.open("x") as output:
            os.chmod(manifest, 0o600)
            json.dump(result, output, indent=2)
        return result
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def restore(source: Path, destination: Path) -> dict[str, Any]:
    manifest = json.loads(source.with_suffix(source.suffix + ".json").read_text())
    if manifest.get("format") != "gridforge-backup-v1" or hashlib.sha256(
        source.read_bytes()
    ).hexdigest() != manifest.get("sha256"):
        raise ValueError("BACKUP_CHECKSUM_FAILURE")
    checked = validate(source)
    if any(manifest.get(key) != value for key, value in checked.items()):
        raise ValueError("BACKUP_MANIFEST_MISMATCH")
    return backup(source, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["backup", "restore", "validate"])
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path, nargs="?")
    args = parser.parse_args()
    if args.operation == "validate":
        result = validate(args.source)
    elif args.destination is None:
        parser.error("destination is required and must not exist")
    else:
        result = (backup if args.operation == "backup" else restore)(args.source, args.destination)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
