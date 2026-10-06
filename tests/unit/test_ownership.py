import os
import subprocess
import sys
from pathlib import Path

import pytest

from edge.runtime.ownership import database_owner


@pytest.mark.skipif(os.name != "posix", reason="POSIX prototype release")
def test_duplicate_owner_rejected_and_crash_releases_lock(tmp_path: Path) -> None:
    path = tmp_path / "edge.db"
    code = (
        "import os,sys; from pathlib import Path; "
        "from edge.runtime.ownership import database_owner; "
        "owner=database_owner(Path(sys.argv[1])); owner.__enter__(); os._exit(0)"
    )
    with database_owner(path):
        duplicate = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True)
        assert duplicate.returncode != 0 and b"EDGE_DATABASE_ALREADY_OWNED" in duplicate.stderr
    assert (
        subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True).returncode == 0
    )
    with database_owner(path):
        assert path.with_name("edge.db.owner.lock").exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX prototype release")
def test_independent_databases_and_memory_can_run(tmp_path: Path) -> None:
    with (
        database_owner(tmp_path / "one.db"),
        database_owner(tmp_path / "two.db"),
        database_owner(None),
    ):
        pass
