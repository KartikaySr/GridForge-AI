"""Pure deterministic synthetic fixture: seed + tick produce identical measurements."""

import math
import random
from datetime import datetime, timedelta
from uuid import UUID, uuid5

from services.telemetry.contracts import TelemetryBatch, TelemetryPoint

ASSETS = ("Chiller", "Compressor", "Extruder", "Crusher", "Pump")
BASE_KW = (920, 710, 1180, 1350, 390)


def factory_batch(
    org: UUID, facility: UUID, seed: int, tick: int, timestamp: datetime, scenario: str
) -> TelemetryBatch:
    rng = random.Random(f"{seed}:{tick}")
    points = []
    for index, base in enumerate(BASE_KW):
        power = base * (1 + 0.05 * math.sin(tick / 12 + index)) + rng.uniform(-5, 5)
        if scenario == "spike":
            power *= 1.4
        points.append(
            TelemetryPoint(
                org_id=org,
                facility_id=facility,
                asset_id=f"SIM-{index + 1}",
                value=round(power * 1000, 3),
                unit="W",
                quality="BAD" if scenario == "bad" else "GOOD",
                event_time=timestamp - timedelta(seconds=30) if scenario == "stale" else timestamp,
                sequence=tick,
                idempotency_key=uuid5(facility, f"{seed}:{tick}:{index}"),
            )
        )
    return TelemetryBatch(points=points)
