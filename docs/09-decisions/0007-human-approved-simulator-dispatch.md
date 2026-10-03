# ADR 0007 — Human-approved simulator dispatch

Status: accepted for Phase 6. Date: 2026-09-28.

The dispatch path accepts only a persisted Phase 5 proposal. It cannot receive arbitrary asset
commands or a client-supplied tenant, role or authorization result. A local native-owned bearer
session is provisioned with fixed `dispatch.read/request/approve/cancel` capabilities for this
simulation prototype; the backend checks capability, facility scope and an eight-hour session
expiry. The UI says this is a local simulation session, not a verified human identity. An
explicit human click with a reason is required for approval. Real identity, separation of duties,
OIDC and full RBAC belong to Phase 10; this local session must never authorize physical writes.

The durable command state is PENDING_APPROVAL → APPROVED → QUEUED → SENT → ACKNOWLEDGED →
EXECUTING → COMPLETED, with REJECTED, CANCELLED and FAILED terminal outcomes. APPROVED and QUEUED
are atomic in one approval transaction. Each transition has actor, reason, UTC time, command
revision and an outbox event. Request/decision UUIDs retain immutable response receipts; same
payload replays and conflicting payloads reject. A command has immutable proposal ID, asset
reductions, duration and simulator behavior. The database permits one active facility command
and one command per run. No client can skip a state or raise limits.

Fresh forecast/risk, registry digest, current telemetry, maintenance, load bounds, asset capability,
policy window and total bound are checked at approval request, approval decision, send and start.
The command stores validation evidence for each stage. A 120-second approval deadline rejects
unanswered requests. The actual simulator execution window must fit policy and forecast horizon.
The native endpoint only permits fixed read/detail/request/decision operations; detail IDs are
parsed as UUIDs before constructing a URL. The local API rejects browser origins and external
role/scope fields. Dispatch rights are checked on the server.

The simulator adapter is an idempotent, durable SQLite acceptance record keyed by command ID.
The worker polls every 0.5 seconds. Normal ACK arrives after one second. An optional delayed ACK
arrives after seven seconds, causing a same-ID retry at five seconds; a missing ACK fails after
two attempts, and a rejected command fails immediately. ACK alone never means success.
Only an ACKNOWLEDGED command that passes another validation can activate the synthetic load
reduction. The telemetry simulator reads the active effect and reduces normalized synthetic kW.
The worker stops the effect on cancellation, failure and elapsed duration. While executing, it
checks telemetry/registry/load bounds and requires monitoring within five seconds. A process
restart fails any unfinished command before workers start and removes the effect. An uncertain
worker/database error fails active work on the next successful transaction.

COMPLETED means the authorized simulator duration elapsed. It is not measured verification or
savings. The simulator never talks to PLC, OPC UA, Modbus or MQTT. The command and outbox, replay
receipts and simulator acceptance are local SQLite durability; cloud sync/ACK is Phase 8.

Migration 5 adds dispatch_commands, dispatch_requests, dispatch_outbox and simulator_commands.
Maximum 500 commands and 5000 mutation receipts reject new requests at capacity rather than
deleting decision history. The accepted simulator action is bounded by the Phase 5 policy,
asset flexibility and current load. Production human identity, operating state history, physical
commissioning, verified response and financial attribution remain future work.
