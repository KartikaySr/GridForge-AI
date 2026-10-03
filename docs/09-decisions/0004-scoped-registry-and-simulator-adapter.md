# ADR 0004 — Scoped registry and read-only simulator adapter

Status: Phase 3 prototype. Supersedes the fixed fixture-only configuration in ADR 0003.

## Domain and persistence

The edge remains a single-facility modular monolith. Organization and facility UUIDs are inherited
from the existing edge identity; neither can be changed through registry editing. Central
PostgreSQL remains the future platform durable authority. This SQLite store is local continuity.

Migration 0002 adds a scoped registry and separate configuration outbox without rewriting
telemetry, identity, sequence or pending telemetry events. Registry bodies are discriminated,
versioned Pydantic documents; SQLite checks kind, JSON validity, uniqueness and positive revisions.
The domain service enforces references and scope inside the same locked transaction as writes.
Unknown migration versions fail closed. A one-time bootstrap imports the original five synthetic
asset identities and mappings, preserving their relationship to Phase 2 history.

Records cover organization, facility/timezone, production line, asset, device, metric and signal
mapping. Assets declare rated load, min/max load, minimum run/off durations, criticality,
capabilities, flexibility/reduction and timezone-aware maintenance windows. Invalid bounds,
critical flexible assets, or reduction without declared capability are rejected. Maintenance
excludes current metadata eligibility and does not stop observation. No optimizer or dispatcher
consumes this metadata yet; eligibility is not operational authority.

Only the commissioned active_power metric/canonical kW and SIMULATOR devices are supported.
Mappings declare asset/device/signal identity, input unit, scale and offset; all are read-only.
One enabled mapping per asset is enforced because current-state storage is one metric per asset.
Enabled references cannot target disabled parents. Disable mappings before assets/devices and
assets before lines. No destructive delete is exposed. The facility and metric catalog remain
single scoped identities; multi-site provisioning and metric families require later migration.

## Edits and events

POST /api/v1/registry takes a typed entity, expected_revision and UUID request_id. Creation
requires revision 0. Updates require the exact current revision. Same-key/same-content replay
returns the original result; conflicting replay or stale revision is rejected. Scope errors,
invalid relations and capacity are explicit. The write and ConfigurationChanged v1 envelope
commit atomically. The envelope has scope, revisioned payload, event/correlation/causation/
idempotency IDs, actor and a durable sequence cursor. It records the local simulation session,
not a provisioned human user. Cloud upload/ACK and user RBAC remain later phases.

The registry is capped at 100 records, 150,000 serialized entity bytes (including per-record
allowance), and 10,000 configuration events. These bounds keep native snapshots below the
256 KiB transport ceiling. Configuration capacity rejects new edits without deleting history.

## Adapter and diagnostics

The simulator polls enabled registry mappings and asset nominal loads, with deterministic
seed/tick/asset variation. It exposes no execute/write method. Incoming points must match an
enabled mapping and registered production line. The normalizer applies raw × scale + offset;
invalid normalized ranges are rejected. Each new point records mapping ID and revision.
Previously stored points remain unchanged and old records may have null mapping provenance.

Device diagnostics distinguish CONNECTED, DEGRADED, DISCONNECTED and DISABLED; recent receipts,
quality/freshness, active mapping count and synthetic scenario inform health. React observes
through authenticated native IPC and does not talk to OT or SQLite. Facilities, Assets and OT
Devices offer scoped editing; the maintenance window editor exposes UTC start/end and reason fields.
The selected revision remains fixed while the registry refreshes, so concurrent edits cannot be
silently overwritten. Failed or uncertain saves preserve the draft and require refresh/review.

Facility timezone controls telemetry presentation; timestamps are normalized to UTC at rest.
Native health/control semantics from Phase 1 remain, and operational_ready stays false.

## Verification boundary

Unit/API tests cover upgrade preservation, validation, hierarchy/disable rules, revision/replay
conflicts, scope escape, maintenance, mapping provenance, read-only protocol boundaries and atomic
rollback. Native tests perform a registry write and verify it survives runtime restart. UI tests
cover conflict handling and browser preview. Production protocol adapters, live equipment,
multi-process store ownership and long-duration capacity qualification are not claimed.
