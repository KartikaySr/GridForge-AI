"""Measured synthetic ingest benchmark; isolated temporary storage, never a production claim."""

import argparse
import json
import statistics
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from edge.storage.repository import Repository
from simulator.factory import factory_batch


def measure(batches: int = 2000) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="gridforge-load-") as directory:
        repo = Repository(Path(directory) / "load.db")
        origin = datetime.now(UTC)
        latencies = []
        started = time.perf_counter()
        for index in range(batches):
            now = origin + timedelta(seconds=index)
            batch = factory_batch(repo.org_id, repo.facility_id, repo.seed, index, now, "normal")
            tick = time.perf_counter()
            assert repo.ingest(batch, now).accepted == 5
            latencies.append((time.perf_counter() - tick) * 1000)
        duration = time.perf_counter() - started
        rows = repo.db.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]
        outbox = repo.db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
        assert rows == outbox == batches * 5
        replay = repo.ingest(batch, now)
        assert replay.duplicates == 5
        result = {
            "mode": "SIMULATION",
            "batches": batches,
            "rows": rows,
            "outbox_rows": outbox,
            "duration_seconds": round(duration, 3),
            "points_per_second": round(rows / duration, 1),
            "ingest_p50_ms": round(statistics.median(latencies), 3),
            "ingest_p95_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 3),
            "ingest_max_ms": round(max(latencies), 3),
            "replay_duplicates": replay.duplicates,
        }
        repo.close()
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batches", type=int, default=2000)
    args = parser.parse_args()
    if not 20 <= args.batches <= 40000:
        parser.error("batches must be between 20 and 40000")
    print(json.dumps(measure(args.batches), indent=2))


if __name__ == "__main__":
    main()
