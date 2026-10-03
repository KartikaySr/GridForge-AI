"""Ephemeral shell health and bounded diagnostic records, not operational state."""

import time
from collections import deque
from datetime import UTC, datetime
from threading import Lock
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from edge.runtime.telemetry import TelemetryRuntime
from uuid import UUID

from edge.runtime.contracts import ComponentHealth, Diagnostics, LogRecord, RuntimeHealth


class RuntimeState:
    def __init__(self, instance_id: UUID) -> None:
        self.telemetry: TelemetryRuntime | None = None
        self.instance_id = instance_id
        self.started_at = datetime.now(UTC)
        self.started_clock = time.monotonic()
        self.logs: deque[LogRecord] = deque(maxlen=100)
        self.discarded_log_count = 0
        self.lock = Lock()
        self.record("runtime.initialized")

    def record(
        self,
        event: str,
        *,
        request_id: UUID | None = None,
        outcome: Literal["success", "denied", "failure"] = "success",
        duration_ms: float | None = None,
    ) -> None:
        with self.lock:
            if len(self.logs) == self.logs.maxlen:
                self.discarded_log_count += 1
            self.logs.append(
                LogRecord(
                    timestamp=datetime.now(UTC),
                    level="INFO" if outcome == "success" else "WARNING",
                    event=event,
                    request_id=request_id,
                    outcome=outcome,
                    duration_ms=duration_ms,
                )
            )

    def health(self) -> RuntimeHealth:
        sync = self.telemetry.sync if self.telemetry else None
        cloud_state: Literal["NOT_CONFIGURED", "CONNECTED", "OFFLINE", "CONFLICT"] = (
            "NOT_CONFIGURED"
            if not sync or not sync.configured
            else "CONFLICT"
            if sync.state == "CONFLICT"
            else "OFFLINE"
            if sync.state == "OFFLINE"
            else "CONNECTED"
        )
        sync_state: Literal["NOT_CONFIGURED", "PENDING", "SYNCHRONIZED", "CONFLICT"] = (
            "NOT_CONFIGURED"
            if not sync or not sync.configured
            else "CONFLICT"
            if sync.state == "CONFLICT" or sync.snapshot_state_has_conflict()
            else "SYNCHRONIZED"
            if sync.state == "SYNCHRONIZED"
            else "PENDING"
        )
        return RuntimeHealth(
            instance_id=self.instance_id,
            facility_id=self.telemetry.repo.facility_id if self.telemetry else None,
            readiness_scope="telemetry" if self.telemetry else "shell-only",
            started_at=self.started_at,
            observed_at=datetime.now(UTC),
            uptime_seconds=round(time.monotonic() - self.started_clock, 3),
            cloud_state=cloud_state,
            sync_state=sync_state,
            components=[
                ComponentHealth(name="local-api", state="READY", detail="Authenticated shell API"),
                ComponentHealth(
                    name="edge-storage",
                    state="READY" if self.telemetry else "NOT_IMPLEMENTED",
                    detail="SQLite WAL with transactional outbox",
                ),
                ComponentHealth(
                    name="telemetry",
                    state="FAILED"
                    if self.telemetry and self.telemetry.failed
                    else "READY"
                    if self.telemetry
                    else "NOT_IMPLEMENTED",
                    detail="Synthetic factory; quality and freshness shown separately",
                ),
                ComponentHealth(
                    name="forecast-risk",
                    state="FAILED"
                    if self.telemetry and self.telemetry.forecasting.worker_error
                    else "READY"
                    if self.telemetry
                    else "NOT_IMPLEMENTED",
                    detail="Baseline worker; data readiness is shown in Forecasting & Risk",
                ),
                ComponentHealth(
                    name="simulation-dispatch",
                    state="FAILED"
                    if self.telemetry and self.telemetry.dispatch.worker_error
                    else "READY"
                    if self.telemetry
                    else "NOT_IMPLEMENTED",
                    detail="Human-approved simulation; no physical control or verified savings",
                ),
                ComponentHealth(
                    name="cloud",
                    state="NOT_CONFIGURED"
                    if cloud_state == "NOT_CONFIGURED"
                    else "FAILED"
                    if cloud_state in ("OFFLINE", "CONFLICT")
                    else "READY",
                    detail="Optional one-way event visibility; local simulation continues offline",
                ),
                ComponentHealth(
                    name="edge-cloud-sync",
                    state="NOT_CONFIGURED"
                    if sync_state == "NOT_CONFIGURED"
                    else "FAILED"
                    if sync_state == "CONFLICT"
                    else "READY",
                    detail="Durable outbox with per-stream acknowledgement; never remote dispatch",
                ),
            ],
        )

    def diagnostics(self) -> Diagnostics:
        with self.lock:
            records = list(self.logs)
            discarded = self.discarded_log_count
        return Diagnostics(
            health=self.health(),
            logs=records,
            log_capacity=100,
            discarded_log_count=discarded,
        )
