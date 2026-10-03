# Phase 8 completion report — edge/cloud synchronization

Date: 2026-09-29. Scope: one-way simulation event synchronization from the desktop edge to a
PostgreSQL cloud inbox. Phase 9 has not begun.

## 1. Implemented

Persistent edge identity, existing transactional outboxes, six independent sync cursors,
bounded batch uploads, cloud edge authentication, committed acknowledgements, idempotent replay,
reconnect/backoff, local continuity while offline, scope/digest/sequence conflict detection,
per-stream quarantine, freshness/backlog status and active Sync Center UI. There is no cloud-to-edge
command channel.

## 2. Files created

`edge/storage/migrations/0007_sync.sql`; `database/migrations/0002_sync.sql`;
`cloud/{__init__,__main__,app,repository}.py`; `services/sync/{__init__,codec,contracts,service}.py`;
`scripts/provision_edge.py`, `scripts/generate_cloud_contracts.py`, generated cloud OpenAPI and
TypeScript client; `tests/unit/test_sync.py` and
`tests/integration/test_sync_postgres.py`; `apps/desktop/src/pages/SyncCenter.tsx` and its
tests; native generated `sync_read` capability; ADR 0009 and this report.

## 3. Files modified

Repository migration/edge identity; local runtime worker, API and health; simulation read
permission; native supervisor, command, build and capability; desktop navigation/status and
bridge; generated OpenAPI/TypeScript client; older migration tests; PostgreSQL Compose mount;
dependency lock, environment example, README, development, configuration/health, API/event
contracts, context index and manifest. The unmounted Phase 0 API remains unchanged.

## 4. Migrations

SQLite v6→v7 adds a durable edge UUID, six cursor rows and append-only conflict audit. The actual
local store preserved **42,100 telemetry rows** and its optimization run. It now has six sync
streams and a stable edge UUID. Pre-upgrade backup: `/private/tmp/gridforge-before-phase8.db`.
PostgreSQL migration adds enrolled edge scope/token digest, per-stream cursor, immutable JSONB
inbox and conflict audit. It is applied on cloud receiver startup, including to an existing
database.

## 5. APIs

Local authenticated GET `/api/v1/sync` exposes state, edge/facility identity, pending totals,
oldest pending time/age, last successful acknowledgement, per-stream cursors and conflicts.
Native `sync_read` is fixed-route and read-only. Cloud GET `/api/v1/sync/state` and POST
`/api/v1/sync/batches` require enrolled edge UUID and 256-bit bearer token; origin and malformed
batches are rejected. Cloud exposes no dispatch or OT write route.

## 6. Events

Six preexisting version-1 outbox families remain unchanged: telemetry, registry, intelligence,
optimization, dispatch and finance. Each upload wraps original event UUID/body with stream,
sequence and canonical digest. PostgreSQL stores the original JSONB event without replaying
domain actions. The cloud cursor and new events commit together; local cursor/outbox flags commit
together after a checked cloud acknowledgement.

## 7. Tests created

Five local Python tests cover v6→v7 preservation and stable identity, generated cloud contract
consistency, authenticated sync status and pending age, transport URL/local sequence guard, and
actual local API ingestion while cloud is down. Five real PostgreSQL integration tests cover the
production HTTP round trip, cloud auth, exact replay, changed replay, atomic gap rejection,
nested scope rejection, lost ACK followed by reconnect, no duplicate dispatch/finance events,
and conflict isolation. Two frontend tests cover browser preview and offline backlog. Native
integration reads Sync Center status from the real local runtime.

## 8. Tests/checks run

`npm run check`: formatting, ESLint/Ruff, TypeScript/strict mypy including cloud code, contract
consistency, frontend/Python tests and production frontend build. `npm run native:check`:
rustfmt, warning-free Clippy and Rust tests. `npm run desktop:build`: native executable with
embedded Phase 8 UI. PostgreSQL tests started a temporary loopback server and shut it down.

## 9. Results

Final suite: **123 Python + 31 frontend + 3 native = 157 tests passed**. Five Python tests used
real temporary PostgreSQL on the verified macOS host; they skip where PostgreSQL test binaries
are absent. Four upstream Starlette/httpx/AnyIO/websockets deprecation warnings remain
non-failing. No remote CI or production deployment result is claimed.

## 10. Manual verification

The actual local SQLite store upgraded in place from v6 to v7 after a backup, with telemetry and
optimization counts unchanged. No cloud endpoint/token is configured for the user's desktop, so
the actual Sync Center will honestly report NOT_CONFIGURED and retain existing outbox records.
The cloud disappearance/reconnect sequence was exercised with a real temporary PostgreSQL
instance and local edge service, not a production cloud account.

## 11. Screens/features

Sync Center shows configured/offline/syncing/synchronized/conflict state, edge/facility UUID,
durable pending total, oldest age, last success, six stream cursors and bounded conflict audit.
Unconfigured setup guidance and browser-preview absence are explicit. Header/System Health now
show actual cloud/sync state rather than a fixed "not implemented" label.

## 12. Limitations

This phase synchronizes events one way for central visibility. It does not deliver cloud commands,
download configuration, build analytics projections, implement a browser/mobile client, rotate
credentials, settle finance or commission physical OT. Cloud deployment and production TLS
termination are not configured here. Conflicts require administrator review; no blind overwrite
or skip operation exists.

## 13. Simulations/mocks

Domain events and dispatch remain SIMULATION-only. Tests use a real PostgreSQL server for cloud
durability and a direct transport shim to deterministically emulate disappearance and a lost
response after commit. Frontend tests mock the native read bridge. The production transport uses
HTTP with trusted HTTPS outside loopback and does not share the test shim.

## 14. Technical debt

Production edge credential storage in the OS, token rotation/revocation UI, cloud deployment,
managed TLS, PostgreSQL role/RLS hardening, retention after ACK, operational observability and
enterprise read projections remain for later work. Catch-up throughput is bounded by 20 events
per batch and five batches per stream per cycle; no multi-site load benchmark was performed.

## 15. Security/safety

Cloud derives org/facility scope from a provisioned edge record, validates event and nested
scope/mode, checks canonical digest and sequence, and stores only a token hash. Edge accepts only
HTTPS or local loopback HTTP; tokens are not exposed through the desktop UI. A cloud outage or
invalid ACK never marks events delivered. Divergent dispatch/finance history is quarantined and
cannot execute a command. The local simulation-session permission gates sync status. Physical
OT writes remain absent.

## 16. Performance

The worker runs every second when configured, attempts at most five 20-event batches per stream
per cycle and backs off from one to 60 seconds after network failure. Batches also cap serialized
payload near 48 KiB; a single oversized event quarantines its stream instead of looping. Both
API request bodies and cloud batches are bounded. Outboxes are retained after ACK; no data
compaction or destructive retention was introduced. Initial local backlog may need several
minutes to catch up, depending on cloud latency and ongoing telemetry rate.

## 17. Documentation

README, development and provisioning walkthrough, configuration/health, API/event contracts,
context index, repository manifest, ADR 0009 and this report were updated. The receiver's
PostgreSQL transaction pattern follows [Psycopg's transaction guidance](https://www.psycopg.org/psycopg3/docs/basic/transactions.html).

## 18. Next phase / approval gate

Phase 9 is AI/RAG/diagnostics, with scoped retrieval and advisory responses. **Awaiting explicit
approval before starting Phase 9.** No model-to-machine path is authorized.
