"""Build an isolated, distributable simulator runtime with no source-checkout dependency."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onedir",
            "--name",
            "gridforge-edge",
            "--paths",
            str(ROOT),
            "--distpath",
            str(ROOT / "packaging/runtime"),
            "--workpath",
            str(ROOT / "packaging/work"),
            "--specpath",
            str(ROOT / "packaging"),
            "--add-data",
            f"{ROOT / 'edge/storage/migrations'}:edge/storage/migrations",
            "--collect-submodules",
            "uvicorn",
            "--collect-all",
            "psycopg_binary",
            str(ROOT / "scripts/frozen_runtime.py"),
        ],
        check=True,
        cwd=ROOT,
    )


if __name__ == "__main__":
    main()
