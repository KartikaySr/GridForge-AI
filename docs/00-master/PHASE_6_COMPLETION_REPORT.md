# Phase 6 completion report — authorization and simulated dispatch

Date: 2026-09-29. Scope: permission checked, human-approved simulator dispatch. Phase 7 has not begun.

## 1. Implemented

Durable approval request/decision, server-owned local-session capability and expiry checks,
optimistic command revisions, strict dispatch state machine, single active command, simulator
acceptance/ACK/effect, bounded retry and timeout, explicit cancellation/rejection/failure,
restart recovery, replay-safe receipts, validation at each authority boundary, timeline/audit.
No automatic approval. No physical control or verified savings.

## 2. Files created

- `services/dispatch/__init__.py`, `contracts.py`, `permissions.py`, `service.py`
- `edge/connectors/dispatch_simulator.py`
- `edge/storage/migrations/0005_dispatch.sql`
- `apps/desktop/src/pages/Dispatch.tsx`, `Dispatch.test.tsx`
- Native generated `dispatch_request` command permission
- `tests/unit/test_dispatch.py`
- ADR 0007 and this report

## 3. Files modified

Repository migration runner; simulator poller; local runtime composition/API, telemetry worker and
health; native supervisor/lib/build/capability; desktop App, runtime bridge and styles;
API-client types/OpenAPI; old migration tests; README, context index, development,
configuration/health, API/event docs and manifest. The old `apps/api/app/main.py` scaffold remains
unmounted; the native desktop uses `edge/runtime/app.py`.

## 4. Migrations

SQLite v4→v5 adds dispatch_commands, dispatch_requests, dispatch_outbox and simulator_commands,
with command/run and request/event uniqueness, transition state checks, a one-active-command
index, and JSON checks. Existing historical upgrade tests now include v5. Actual local upgrade
preserved 24,095 prior telemetry payloads and the prior optimization run without loss or change.
Temporary pre-upgrade backup: `/private/tmp/gridforge-before-phase6.db`.

## 5. APIs

Authenticated GET `/api/v1/dispatch`, POST `/api/v1/dispatch/requests`, POST
`/api/v1/dispatch/decisions`, GET `/api/v1/dispatch/{command_id}`, GET
`/api/v1/dispatch/events?after=N`. The native bridge allowlists read/detail/request/decision,
parses detail UUIDs and rejects arbitrary paths. OpenAPI/TypeScript contracts regenerated.

## 6. Events

ApprovalRequested/Granted/Rejected; DispatchQueued/Sent/Retried/Acknowledged/Executing/
Completed/Failed/Cancelled/Rejected. Version 1 envelopes include facility scope, actor, UTC
time, command revision, before/after states, reason and correlation/causation IDs. State changes,
simulator acceptance and outbox events commit together in local SQLite. Cloud ACK is Phase 8.

## 7. Tests created

13 dispatch Python tests cover approval/denial/scope/session expiry, idempotent request and
decision replay, revision conflict, changed configuration, timeout, normal/delayed/missing ACK,
failed simulator command, same-ID retry, cancellation and synthetic load restoration, full
300-second simulated completion, disconnect/monitoring gap, restart recovery, event-write rollback,
strict API roles/fields, and v4→v5 migration. Three frontend tests cover preview/empty/unavailable
states. Native existing integration test now reads Dispatch and rejects path injection.

## 8. Tests/checks run

`npm run check`: formatting, ESLint/Ruff, TypeScript/strict mypy, contract consistency, frontend
and Python tests, frontend production build. `npm run native:check`: rustfmt, warning-free Clippy,
Rust unit/integration/doc tests. `npm run desktop:build`: native debug build with embedded UI.
Targeted dispatch tests were run while resolving transition and freshness issues.

## 9. Results

All final checks passed: **108 Python + 27 frontend + 3 native = 138 tests**. Two pre-existing
upstream Starlette/httpx/AnyIO deprecation warnings remain non-failing. No remote CI claim.

## 10. Manual verification

Launched the new native desktop, opened Dispatch and verified the local simulation-session
notice, session expiry, empty durable queue and disabled Request approval button when the latest
optimization run was infeasible. The first smoke run showed an intermittent combined-read error;
sequential native reads fixed it. Rebuilt and verified live state, then closed the QA app cleanly.
The fully approved positive path was validated automatically with the real SQLite simulator and
telemetry adapter, not claimed as a manual UI demonstration.

## 11. Screens/features

Active Dispatch page: proposal context, behavior choice, human request, explicit approve/reject/
cancel with reason, permission/status/expiry disclosure, queue, selected command, actions,
state timeline, validation evidence, and same-request-ID retry. Loading, empty, unavailable and
historical states are explicit. Browser preview cannot issue commands.

## 12. Limitations

The local session is not a verified person or production separation of duties. All normal native
sessions receive fixed simulation permissions; Phase 10 must add real RBAC/identity. Only one
active command is allowed per facility. Unverified minimum run/off requirements remain blocked by
Phase 5. Restart conservatively fails unfinished commands; it does not resume execution.

## 13. Simulations/mocks

The simulator adapter accepts and ACKs commands in SQLite and adjusts synthetic telemetry. The
UI can choose delayed ACK, missing ACK or rejected-command scenarios to exercise failure paths.
Frontend tests mock the native bridge; Python/native tests exercise real local services and DB.
COMPLETED denotes elapsed synthetic duration, not measured verification or real savings.

## 14. Technical debt

Central identity/OIDC, role management, separation of duties, production session storage,
physical OT commissioning, cloud sync/ACK, finer job metrics and signed portable packaging remain
later work. The desktop still has a source-checkout/.venv development dependency. A real utility
bill, dispatch settlement and verified savings do not exist in this phase.

## 15. Security/safety

Server checks fixed capabilities, org/facility scope and expiry; hidden UI buttons alone do not
grant permission. Only saved proposals can create commands; client scope/role/override fields
reject. Hard constraints and fresh evidence are rechecked at request, approval, send and start.
No ACK means no execution. Unexpected gap, bad data, configuration change or restart stops the
synthetic effect/fails the command. Command ID, request UUID and revision prevent replay/skipped
states. No PLC/OPC UA/Modbus/MQTT write code exists.

## 16. Performance

Worker polls every 0.5 seconds. Latest 20 commands and 100-event cursor pages bound API reads;
500-command and 5000-receipt capacities reject extra writes rather than deleting audit history.
Active simulation effects come from indexed local records. Full load/soak or production latency
benchmark was not performed; synthetic local tests do not establish production throughput.

## 17. Documentation

README, context index, ADR 0007, API/event contracts, development walkthrough, configuration
and health, repository manifest and this 18-point report updated. Historical reports retained.

## 18. Next phase / approval gate

Phase 7: quality-gated baseline/actual verification, estimated versus verified simulated savings,
versioned tariff assumptions and finance provenance. **Awaiting explicit approval to start Phase 7.**
Physical OT writes remain outside the authorized prototype scope.
