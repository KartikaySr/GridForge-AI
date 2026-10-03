# SDLC, Testing, Failure Handling & Observability

## Phases

0 repository quality/CI; 1 Tauri shell + local runtime health; 2 local DB + deterministic simulator + live telemetry;
3 facility/assets/devices/signal mapping; 4 forecast/risk; 5 constraints/optimization; 6 approval/dispatch simulation;
7 verification/finance; 8 cloud sync/outbox; 9 AI/RAG; 10 RBAC/observability/packaging/hardening; 11 final integrated simulated demonstration and offline reconciliation.
Do not jump phases without approval.

## Tests

Unit: calculations/constraints/transitions/validators.
Contract: TS/Python API/event compatibility.
Repository: migrations/constraints/RLS.
Integration: API+DB+worker, runtime+simulator, sync.
E2E: launch -> live telemetry -> risk -> proposal -> approval -> simulated dispatch -> verification -> savings.
ML: leakage/deterministic features/time-split/degraded input.
Security: authz matrix/tenant isolation/replay/AI guardrails.
Performance: sustained ingestion, queues, charts, query budgets.
Chaos: cloud loss, connector loss, delayed ACK, duplicates, worker restart, bad payload.

## Required failures

Cloud offline: local permitted operations continue; sync pending.
DB unavailable: safely stop state-changing workflows.
Telemetry stale/bad: mark and degrade forecast/optimization.
Device offline: remove unavailable flexibility.
Forecast failure: unknown/degraded.
Optimizer infeasible: explicit reasons.
Approval timeout: no surprise auto-send.
No dispatch ACK: fail/unknown, never assume success.
Duplicate command: return existing via idempotency.
Crash: recover durable command/outbox.
AI down: core works.
Tariff missing: finance incomplete, never invent.

## Observability

Structured logs: timestamp, level, component, event, request/trace/correlation IDs, safe scope, duration/outcome/error.
Metrics: ingestion/rejected/stale/queue, connector health, forecast/optimizer latency/errors, dispatch ACK/failure,
sync pending/age/conflicts, API/DB, AI. Trace the full decision chain.
Diagnostics bundle must be redacted.

## Golden acceptance demo

All synthetic and labeled SIMULATED: five assets -> 1Hz normal -> deterministic spike -> forecast threshold breach ->
risk evidence -> candidate matrix with at least one hard rejection -> proposal -> human simulated approval ->
dispatch states -> simulator load response -> verification -> VERIFIED SIMULATED savings -> linked audit -> AI explanation.
Also demonstrate cloud disconnect/local continuity/reconnect without duplicates.
