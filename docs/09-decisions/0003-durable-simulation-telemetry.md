# ADR 0003 — Durable simulation telemetry

Status: accepted for Phase 2 prototype. No OT actuation is introduced.

## Decision

Keep the modular monolith. The pure deterministic factory fixture emits five active-power
signals. Shared Pydantic contracts validate identity, source, units, finite values, sequence and
UTC timestamps. The edge runtime admits at most eight batches and acknowledges after a SQLite
transaction commits normalized points, latest-state pointers, counters, simulator tick and
versioned TelemetryReceived outbox envelopes. SQL migration 0001 is applied transactionally with
PRAGMA user_version; unknown versions fail closed. WAL and foreign keys are enabled.

Organization/facility UUIDs are generated and persisted once. The server fixes all reads to its
single commissioned synthetic scope and rejects mismatched writes. Asset/device/line identifiers
are a narrow simulation fixture, not a replacement for Phase 3 registry or Phase 10 RBAC.

Ingest preserves event and received timestamps. W becomes kW. Source BAD, age over five seconds,
future skew over two seconds, synthetic plausibility outliers and out-of-order arrivals are
explicit flags. Late/future points remain in history/outbox without replacing newer trustworthy
state. Other bad measurements may replace current state but cannot contribute to a live total.
The 10,000 kW outlier threshold is a synthetic plausibility rule, never an equipment safety limit.

An authenticated SSE connection publishes complete bounded snapshots near 1 Hz. The native
transport owns the token and reconnects; a snapshot includes durable cursor and recent history.
This is current-state resynchronization, not guaranteed delivery of every sample through SSE.
Consumers needing every committed point use paginated telemetry or ordered event history.
The webview polls the native snapshot and never receives a token, runtime URL or OT capability.
History and scenario commands are narrow, allowlisted Tauri capabilities.

## Capacity and failure behavior

No raw telemetry or pending outbox is silently deleted. Admission, malformed/rejected and replay
counters are visible. At 250,000 persisted points ingestion rejects new points; safe outbox ACK
and retention management are deferred to Phase 8. Default demo capacity is about 13.9 hours from
empty. Queue contents are not durable until committed/acknowledged; callers retry interrupted
batches idempotently. SQLite errors mark the worker failed and API failures degrade the native
supervisor. Startup migration failure prevents readiness.

The local-only scenario resets to normal on restart. Simulation identity, sequence and records
survive. No persistent bearer credentials are added. Cloud, operational authorization, forecast,
optimizer, dispatch and savings remain unavailable.

## Validation and consequences

Repository tests cover migration rejection, replay/scope rollback, normalization, quality,
capacity and recovery. Real-process tests exercise authenticated SSE/reconnection. Native tests
verify actual simulator samples and durable identity after restart. UI tests suppress totals
for bad/stale/disconnected state. The explorer bounds rendering and pages history by row cursor.
A 5,000-point local benchmark measured 0.795 s ingest and 3.238 ms mean state+recent query time;
this is development evidence, not an industrial throughput or long-running availability claim.
