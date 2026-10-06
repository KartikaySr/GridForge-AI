import json
import subprocess
import sys
from pathlib import Path

import pytest

from edge.storage.repository import Repository
from services.operations.recovery import backup, restore, validate
from services.security.audit import AuditService
from tests.unit.test_telemetry import NOW, batch


def test_live_backup_restore_replay_and_no_overwrite(tmp_path: Path) -> None:
    source, saved, recovered = (
        tmp_path / name for name in ["live.db", "backup.db", "recovered.db"]
    )
    repo = Repository(source)
    incoming = batch(repo)
    repo.ingest(incoming, NOW)
    AuditService(repo).record("test", "success")
    result = backup(source, saved)
    assert result["schema_version"] == 11
    repo.ingest(batch(repo, 2), NOW)
    restore(saved, recovered)
    restored = Repository(recovered)
    assert restored.facility_id == repo.facility_id
    assert len(restored.history()) == len(restored.events()) == 5
    assert restored.ingest(incoming, NOW).duplicates == 5
    assert AuditService(restored).verify()
    with pytest.raises(FileExistsError):
        restore(saved, source)
    manifest = saved.with_suffix(".db.json")
    manifest.write_text(json.dumps(result | {"sha256": "invalid"}))
    with pytest.raises(ValueError, match="CHECKSUM"):
        restore(saved, tmp_path / "bad.db")
    restored.close()
    repo.close()


def test_abrupt_process_exit_recovers_committed_wal_and_outbox(tmp_path: Path) -> None:
    path = tmp_path / "crash.db"
    code = """import os,sys
from pathlib import Path
from edge.storage.repository import Repository
from tests.unit.test_telemetry import batch,NOW
repo=Repository(Path(sys.argv[1]))
repo.ingest(batch(repo),NOW)
repo.db.execute("UPDATE counters SET value=99999 WHERE name='accepted'")
os._exit(23)
"""
    result = subprocess.run([sys.executable, "-c", code, str(path)], timeout=10)
    assert result.returncode == 23
    repo = Repository(path)
    assert repo.state()[2]["accepted"] == 5
    assert len(repo.history()) == len(repo.events()) == 5
    repo.close()
    assert validate(path)["schema_version"] == 11
