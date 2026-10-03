import math
import random
from datetime import datetime, timedelta
from uuid import uuid5

from edge.connectors.dispatch_simulator import DispatchSimulator
from services.registry.contracts import Asset, Device, SignalMapping
from services.registry.service import RegistryService
from services.telemetry.contracts import TelemetryBatch, TelemetryPoint


class SimulatorAdapter:
    """Simulator poller; only durable authorized dispatch effects can modify synthetic loads."""

    def __init__(self, registry: RegistryService) -> None:
        self.registry = registry

    def poll(self, tick: int, timestamp: datetime, scenario: str) -> TelemetryBatch | None:
        if scenario == "disconnected":
            return None
        reductions = DispatchSimulator(self.registry.repo).reductions(timestamp)
        records = self.registry.records()
        assets = {r.entity.id: r.entity for r in records if isinstance(r.entity, Asset)}
        devices = {r.entity.id: r.entity for r in records if isinstance(r.entity, Device)}
        points = []
        for record in records:
            mapping = record.entity
            if not isinstance(mapping, SignalMapping) or not mapping.enabled:
                continue
            asset, device = assets[mapping.asset_id], devices[mapping.device_id]
            if not asset.enabled or not device.enabled or "telemetry" not in asset.capabilities:
                continue
            rng = random.Random(f"{self.registry.repo.seed}:{tick}:{asset.id}")
            power = max(0, asset.rated_kw * (1 + 0.05 * math.sin(tick / 12)) + rng.uniform(-5, 5))
            if scenario == "spike":
                power *= 1.4
            raw = power * (1000 if mapping.input_unit == "W" else 1)
            if asset.id in reductions:
                canonical = raw * mapping.scale + mapping.offset
                reduced = max(asset.min_load_kw, canonical - reductions[asset.id])
                raw = max(0, (reduced - mapping.offset) / mapping.scale)
            points.append(
                TelemetryPoint(
                    org_id=asset.org_id,
                    facility_id=asset.facility_id,
                    asset_id=asset.id,
                    line_id=asset.line_id,
                    device_id=device.id,
                    signal_id=mapping.signal_id,
                    value=round(raw, 3),
                    unit=mapping.input_unit,
                    quality="BAD" if scenario == "bad" else "GOOD",
                    event_time=timestamp - timedelta(seconds=30)
                    if scenario == "stale"
                    else timestamp,
                    sequence=tick,
                    idempotency_key=uuid5(asset.facility_id, f"adapter-v1:{tick}:{mapping.id}"),
                )
            )
        return TelemetryBatch(points=points) if points else None
