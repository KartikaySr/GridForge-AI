# Phase 5 completion report — constraints and optimization

Date: 2026-09-28. Scope: simulation-only advisory optimization. Phase 6 has not begun.

## 1. Implemented

Immutable, effective-dated simulation policies; hard/soft constraint evaluation; explicit asset
flexibility; deterministic candidate generation and penalty-based allocation; PROPOSED,
INFEASIBLE and NO_ACTION outcomes; expected reduction and optional Decimal economic estimate;
durable evidence, replay protection and transactional audit outbox; native desktop workflow.

## 2. Files created

- `services/optimization/__init__.py`, `contracts.py`, `engine.py`, `service.py`
- `edge/storage/migrations/0004_optimization.sql`
- `apps/desktop/src/pages/Optimization.tsx`, `Optimization.test.tsx`
- Native generated optimization-request command permission
- `tests/unit/test_optimization.py`, `tests/__init__.py`, `tests/unit/__init__.py`
- ADR 0006 and this report

## 3. Files modified

Runtime composition/API and repository migration runner; native supervisor/lib/build/capability;
frontend App, runtime bridge and styles; API-client exports, OpenAPI and generated TypeScript;
existing registry/forecast migration tests; README, context index, manifest, development,
configuration/health and API/event documentation. Legacy `apps/api/app/main.py` is unchanged:
the operational desktop uses `edge/runtime/app.py`, not that illustrative scaffold.

## 4. Migrations

SQLite v3 → v4: optimization_policies, optimization_runs, optimization_outbox. Immutable payloads,
unique request/event identities, policy FK, valid JSON checks and ordered sequences. Upgrade tests
cover old schemas. Actual local DB upgrade preserved all 12,880 pre-existing telemetry payloads;
zero missing or modified. Backup: `/private/tmp/gridforge-before-phase5.db` (temporary, not a
production backup strategy). No central Postgres migration or production rollout claimed.

## 5. APIs

Authenticated GET optimization snapshot; POST policy; POST run; GET run history (one full run per
exclusive sequence cursor); GET event history (100 per page). All under `/api/v1/optimization`.
Native optimization_request allowlists read/policy/run/history operations. Extra fields and client
scope/action overrides reject. OpenAPI is regenerated and consistency checked.

## 6. Events

OptimizationPolicyCreated, OptimizationStarted, ProposalCreated, OptimizationInfeasible,
OptimizationNoAction, schema v1. Scope, actor, UTC time, resource and correlation/causation IDs.
Run/start/result events commit together. Outbox upload/ACK remains Phase 8.

## 7. Tests created

22 Python cases cover real simulator ingestion → forecast → proposal, rejected assets, soft
preference ordering, exact money, missing rates, no action, hard exclusions, runtime/downtime,
maintenance overlap, stale/future/bad/missing telemetry, mapping/device failures, policy cap/window/
duration, configuration changes, auth/Origin/scope/override denial, idempotency/conflicts, restart,
migrations, capacity and transaction rollback. Four UI tests cover preview, empty, unavailable and
same-ID retry. Existing native integration test now exercises policy/run/read and route denial.

## 8. Tests/checks run

`npm run check`: Prettier/Ruff formatting, ESLint/Ruff, TypeScript/strict mypy, generated contract
consistency, Vitest, pytest and production frontend build.
`npm run native:check`: rustfmt, Clippy with warnings denied, Rust integration/unit/doc tests.
`npm run desktop:build`: native development build with embedded UI.
Targeted tests were run while implementing and fixing identified issues.

## 9. Results

All final checks passed: **95 Python + 24 frontend + 3 native = 122 tests**. Two existing upstream
Starlette/httpx/AnyIO deprecation warnings remain non-failing. Initial sandboxed process tests
could not bind loopback; rerun with local socket permissions passed. No remote CI claim.

## 10. Manual verification

Launched the new native build. The temporary QA bundle initially displayed a blank webview;
activating it/resetting zoom exposed the rendered app (also seen in earlier phase QA). Created
“Phase 5 UI smoke test” through the form, selected the saved policy and generated INFEASIBLE.
Verified missing-threshold/forecast gates, five rejected candidates, expanded hard/soft results,
run count and three pending audit events. Closed the QA app cleanly. Its labeled policy/run remain
in local simulation history. Positive proposal and estimated-money paths were verified automatically
with simulator ingestion, not claimed as a full manual positive-path demonstration.

## 11. Screens/features

Constraints & Optimization is active: versioned policy form/selector, bounded run request,
candidate matrix with all constraints, proposal/explanation/estimated value, traceability snapshot,
older/latest navigation, empty/loading/unavailable/history states and retry with stable request ID.
UI evidence expires independently of retained historical results. No dispatch controls.

## 12. Limitations

Continuous constant curtailment only. No shifting, rebound schedule, discrete start/stop solver,
production scheduling, calibrated flexibility forecast or production economic optimum. Nonzero
runtime/downtime requirements block until authoritative history exists. Five-second evidence expiry
requires fresh evaluation for any future dispatch. Local simulation session is not human RBAC.

## 13. Simulations/mocks

All source measurements and proposed actions are simulated. A supplied energy rate is a synthetic
policy assumption, not a utility tariff. Gross avoided-energy estimate excludes rebound, production
costs, demand charges and settlement; it is never verified savings. UI tests mock the native bridge;
backend/native tests also exercise real services and SQLite. No fake optimizer success endpoint.

## 14. Technical debt

Runtime-state history, scheduling/shift optimizers and richer preference editors are future extensions.
Central durable replication/RLS, human identity/RBAC, signed packaging, portable Python and full
observability remain their planned phases. The temporary QA bundle activation quirk is documented;
the standard native developer flow and automated native tests remain available.

## 15. Security/safety

No physical actuation or command adapter. Hard gates cannot be overridden via API or soft scores.
Unknown/stale inputs fail closed. Server owns scope. Bearer/Origin checks, body bounds, strict models,
fixed native routes, immutable policy/run records and replay conflicts remain enforced. Every proposal
is NOT_AUTHORIZED. Phase 6 must revalidate all current constraints before simulated execution.

## 16. Performance

Registry bounds limit candidate count; sorting is O(A log A). Policies capped at 100, runs at 500;
outbox bounded to at most 1100 events before later sync/retention work. One full run per history
page, 100 events per page, 64 KiB requests, 2 MiB native optimization GET response bound. Other
native GET responses retain 256 KiB. Work is synchronous under the repository lock; no production
load benchmark or multi-facility throughput claim.

## 17. Documentation

README/context index, development walkthrough, configuration/health, executable API/event reference,
ADR 0006, repository manifest and this 18-point report updated. Historical reports retained.

## 18. Next phase / approval gate

Phase 6: permissions, human approval decisions, durable simulated dispatch state machine, adapter,
acknowledgement/timeout/retry/cancel/replay handling, timeline and audit. **Awaiting the user's
explicit approval before starting Phase 6**, as requested. Physical OT writes remain out of scope.
