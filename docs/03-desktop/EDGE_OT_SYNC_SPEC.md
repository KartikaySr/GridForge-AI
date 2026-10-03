# Edge Runtime, OT & Cloud Sync

## Edge runtime

Supervise local API/workers; local state; telemetry normalization; inference; risk; optimization; command state;
verification; outbox/sync; health. Local API binds loopback and authenticates IPC. Long workers expose health/restart.

## Local DB

SQLite prototype with WAL+migrations for edge identity/config, recent telemetry/aggregates, command state, outbox,
sync cursor and audit/security. Secrets belong in OS credential storage.

## Backpressure/time

Bounded queues; never silently drop. Preserve command/audit over raw telemetry and expose rejected/dropped counters.
Record source and received timestamps, detect clock skew, UTC at rest.

## OT adapters

Common interface: connect/disconnect/health, metadata/discovery where supported, subscribe/poll, normalize, and
execute only via dispatch adapter contract. SIMULATOR first; OPC UA/Modbus TCP/MQTT are future targets.
Raw tag/register/topic -> canonical metric/asset/unit/scale/type/quality/writable mapping. Mappings versioned/audited.
GridForge is not a safety PLC. Existing interlocks remain authoritative. Real writes disabled by default.

## Simulator

Deterministic seed; normal profiles; spikes; disconnects; stale/outlier/bad quality; delayed ACK; failed command.

## Sync

Transactional local state + outbox. Upload batches with event/idempotency IDs; compact only after durable ACK.
Telemetry append-only; commands preserve transition history; config versioned/conflict-aware; audit append-only;
finance never blind-overwrites. Reconnect: auth -> cursors/versions -> pending upload -> allowed download ->
reconcile -> synchronized. UI shows pending count/age/conflicts.
