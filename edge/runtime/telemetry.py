import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path

from edge.connectors.simulator import SimulatorAdapter
from edge.storage.repository import CapacityError, Rejected, Repository
from services.dispatch.service import DispatchService
from services.finance.service import FinanceService
from services.forecasting.service import ForecastService
from services.registry.contracts import (
    Asset,
    ConnectorHealth,
    Device,
    Facility,
    RegistrySnapshot,
    SignalMapping,
)
from services.sync.service import SyncService
from services.telemetry.contracts import (
    AssetState,
    IngestResult,
    TelemetryBatch,
    TelemetrySnapshot,
)


class TelemetryRuntime:
    def __init__(self, path: Path | None, simulate: bool = True) -> None:
        self.repo = Repository(path)
        self.simulate = simulate
        self.adapter = SimulatorAdapter(self.repo.registry)
        self.forecasting = ForecastService(self.repo)
        self.dispatch = DispatchService(self.repo, self.forecasting)
        self.finance = FinanceService(self.repo)
        self.sync = SyncService(
            self.repo,
            os.environ.get("GRIDFORGE_CLOUD_URL"),
            os.environ.get("GRIDFORGE_EDGE_TOKEN"),
        )
        self.queue: asyncio.Queue[
            tuple[TelemetryBatch, int | None, asyncio.Future[IngestResult]]
        ] = asyncio.Queue(maxsize=8)
        self.scenario = "normal"
        self.failed = False
        self.tasks: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        self.dispatch.recover()
        self.tasks.append(asyncio.create_task(self.dispatch_loop()))
        self.tasks.append(asyncio.create_task(self.finance_loop()))
        self.tasks.append(asyncio.create_task(self.sync_loop()))
        self.tasks.append(asyncio.create_task(self.consume()))
        self.tasks.append(asyncio.create_task(self.infer()))
        if self.simulate:
            self.tasks.append(asyncio.create_task(self.produce()))

    async def close(self) -> None:
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        try:
            self.dispatch.recover()
        finally:
            self.repo.close()

    async def dispatch_loop(self) -> None:
        while True:
            work = asyncio.create_task(
                asyncio.to_thread(
                    self.dispatch.tick,
                    self.failed or self.scenario != "normal" and self.scenario != "spike",
                )
            )
            try:
                await asyncio.shield(work)
            except asyncio.CancelledError:
                await work
                raise
            await asyncio.sleep(0.5)

    async def finance_loop(self) -> None:
        while True:
            work = asyncio.create_task(asyncio.to_thread(self.finance.tick))
            try:
                await asyncio.shield(work)
            except asyncio.CancelledError:
                await work
                raise
            await asyncio.sleep(5)

    async def sync_loop(self) -> None:
        while True:
            work = asyncio.create_task(asyncio.to_thread(self.sync.tick))
            try:
                await asyncio.shield(work)
            except asyncio.CancelledError:
                await work
                raise
            await asyncio.sleep(1)

    async def infer(self) -> None:
        while True:
            work = asyncio.create_task(
                asyncio.to_thread(
                    self.forecasting.tick, self.failed or self.scenario == "disconnected"
                )
            )
            try:
                await asyncio.shield(work)
            except asyncio.CancelledError:
                await work  # Join the DB user before closing the shared connection.
                raise
            await asyncio.sleep(5)

    async def submit(self, batch: TelemetryBatch, tick: int | None = None) -> IngestResult:
        if self.failed:
            raise CapacityError("WORKER_FAILED")
        future: asyncio.Future[IngestResult] = asyncio.get_running_loop().create_future()
        try:
            self.queue.put_nowait((batch, tick, future))
        except asyncio.QueueFull:
            self.repo.count("backpressure", len(batch.points))
            raise CapacityError("QUEUE_FULL") from None
        return await future

    async def consume(self) -> None:
        while True:
            batch, tick, future = await self.queue.get()
            try:
                if self.failed:
                    raise CapacityError("WORKER_FAILED")
                result = self.repo.ingest(batch, datetime.now(UTC), tick)
                if not future.done():
                    future.set_result(result)
            except (Rejected, CapacityError) as error:
                failure: Exception = error
                try:
                    self.repo.count("rejected", len(batch.points))
                except Exception:
                    self.failed = True
                    failure = CapacityError("WORKER_FAILED")
                if not future.done():
                    future.set_exception(failure)
            except Exception:
                self.failed = True
                if not future.done():
                    future.set_exception(CapacityError("WORKER_FAILED"))
            finally:
                self.queue.task_done()

    async def produce(self) -> None:
        while True:
            try:
                if self.scenario != "disconnected" and not self.failed:
                    tick = self.repo.state()[0] + 1
                    batch = self.adapter.poll(tick, datetime.now(UTC), self.scenario)
                    if batch is not None:
                        await self.submit(batch, tick)
            except (Rejected, CapacityError):
                pass  # Rejection/backpressure is counted; retained data is never evicted.
            except Exception:
                self.failed = True
            await asyncio.sleep(1)

    def snapshot(self) -> TelemetrySnapshot:
        tick, points, counts, pending = self.repo.state()
        now = datetime.now(UTC)
        current = {point.asset_id: point for point in points}
        assets = []
        records = self.repo.registry.records()
        fixture_assets = [r.entity for r in records if isinstance(r.entity, Asset)]
        facility = next(r.entity for r in records if isinstance(r.entity, Facility))
        mapped_assets = {
            r.entity.asset_id
            for r in records
            if isinstance(r.entity, SignalMapping) and r.entity.enabled
        }
        for asset in fixture_assets:
            asset_id, label = asset.id, asset.name
            point = current.get(asset_id)
            status = "EMPTY"
            if (
                self.scenario == "disconnected"
                or self.failed
                or not asset.enabled
                or asset_id not in mapped_assets
                or "telemetry" not in asset.capabilities
            ):
                status = "DISCONNECTED"
            elif point is not None:
                if (now - point.event_time).total_seconds() > 5:
                    status = "STALE"
                elif point.flags or point.quality == "BAD":
                    status = "BAD"
                else:
                    status = "LIVE"
            assets.append(
                AssetState.model_validate(
                    dict(asset_id=asset_id, label=label, point=point, status=status)
                )
            )
        recent = self.repo.history(limit=100)
        return TelemetrySnapshot(
            observed_at=now,
            org_id=self.repo.org_id,
            facility_id=self.repo.facility_id,
            facility_name=facility.name,
            timezone=facility.timezone,
            seed=self.repo.seed,
            tick=tick,
            scenario=self.scenario,
            worker_state="FAILED" if self.failed else "RUNNING",
            cursor=recent[0].row_id if recent else 0,
            assets=assets,
            recent=recent,
            accepted=counts["accepted"],
            duplicates=counts["duplicates"],
            rejected=counts["rejected"],
            backpressure=counts["backpressure"],
            queue_depth=self.queue.qsize(),
            queue_capacity=self.queue.maxsize,
            pending_outbox=pending,
            storage_capacity=self.repo.capacity,
            storage_full=counts["accepted"] >= self.repo.capacity,
        )

    def registry_snapshot(self) -> RegistrySnapshot:
        records = self.repo.registry.records()
        now = datetime.now(UTC)
        points = self.repo.state()[1]
        connectors = []
        for record in records:
            device = record.entity
            if not isinstance(device, Device):
                continue
            mappings = [
                r.entity
                for r in records
                if isinstance(r.entity, SignalMapping)
                and r.entity.device_id == device.id
                and r.entity.enabled
            ]
            received = max(
                (p.received_time for p in points if p.device_id == device.id), default=None
            )
            device_points = [p for p in points if p.device_id == device.id]
            state = "CONNECTED"
            if not device.enabled:
                state = "DISABLED"
            elif self.scenario == "disconnected":
                state = "DISCONNECTED"
            elif (
                self.failed
                or not mappings
                or received is None
                or (now - received).total_seconds() > 5
                or self.scenario in ("bad", "stale")
                or any(
                    p.quality != "GOOD" or p.flags or (now - p.event_time).total_seconds() > 5
                    for p in device_points
                )
            ):
                state = "DEGRADED"
            connectors.append(
                ConnectorHealth.model_validate(
                    dict(
                        device_id=device.id,
                        state=state,
                        mapping_count=len(mappings),
                        last_received_at=received,
                        detail="Simulation only; no physical writes. Inspect mappings and quality.",
                    )
                )
            )
        with self.repo.lock:
            pending = self.repo.db.execute(
                "SELECT COUNT(*) FROM configuration_outbox WHERE acknowledged=0"
            ).fetchone()[0]
        return RegistrySnapshot(
            org_id=self.repo.org_id,
            facility_id=self.repo.facility_id,
            records=records,
            connectors=connectors,
            flexibility_available=[
                r.entity.id
                for r in records
                if isinstance(r.entity, Asset) and r.entity.flexibility_available(now)
            ],
            pending_configuration_events=pending,
        )
