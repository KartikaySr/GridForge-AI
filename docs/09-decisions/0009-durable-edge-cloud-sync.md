# ADR 0009 — Durable one-way edge/cloud sync

Status: accepted for Phase 8. Date: 2026-09-29.

The edge remains the local operational control plane when cloud connectivity disappears.
The cloud receiver is a separate FastAPI process backed by PostgreSQL and only accepts
append-only, versioned events for enterprise visibility. It has no route that can approve,
dispatch, cancel or write to an OT adapter. Future Web/Mobile clients must use shared event/API
contracts rather than importing Tauri or local SQLite code.

SQLite v7 assigns a persistent edge UUID and six independent stream cursors. The preexisting
telemetry, configuration, intelligence, optimization, dispatch and finance outboxes remain the
source of unsent events; domain mutations already commit with those outboxes. The worker builds
bounded contiguous batches, preserving event UUID, schema version, org/facility scope and a
canonical payload digest. It contacts only an environment-configured HTTPS endpoint (loopback
HTTP for development). Tokens are provisioned out of band, never hardcoded or sent to the UI.

PostgreSQL stores edge enrollment, SHA-256 token digest, per-stream cursor, immutable JSONB
events and conflict audit. The receiver authenticates the edge and derives scope from enrollment;
it validates nested scope/mode and enforces sequential inserts under a cursor row lock. Events
and cursor commit in one transaction. Exact replay acknowledges without another insert. A
different event or digest at the same sequence, missing sequence, reused event UUID or scope
escape rejects the whole batch. Edge acknowledgement updates its cursor and outbox flags in one
SQLite transaction only after a checked cloud receipt. A cloud commit followed by response loss
therefore replays safely. A cloud outage leaves local telemetry and simulated dispatch active.

On reconnect, the worker fetches remote cursors, detects cloud rewind/ahead divergence and
replays local pending rows. Per-stream conflicts are audited and quarantined without deleting
or overwriting data; unaffected streams continue. Sync Center shows backlog, oldest pending
age, last success and each cursor. There is no automatic conflict resolution, since choosing
which divergent dispatch or finance history to trust requires administrative review. PostgreSQL
central event storage is durable truth for received history; normalized enterprise projections,
RLS roles, cloud deployment, token rotation and production credential storage remain future
work. Simulation mode and `operational_ready=false` remain unchanged.
