# Phase 11 — integrated demonstration and desktop simulation completion

The desktop simulation milestone is complete. Web/mobile development has not started; the corporate operating model and foundation requirements are ready for the next stage. Physical OT operation and production distribution remain separately gated.

## 1. Implemented

An integrated desktop rehearsal covers normal factory → bad-data UNKNOWN → recovered demand peak → forecast/risk → constraint evaluation → proposal → explicit operator approval → simulated dispatch/load response → measured verification → verified synthetic savings → audit → cited advisory explanation. Real PostgreSQL/HTTP acceptance also covers disconnected cloud, local continuity, pending events and reconciliation. No manual database manipulation is used.

## 2. Files created

`services/demonstration/` contracts/service; desktop Demonstration page and tests; disposable real receiver helper and canonical runner; unit/integration acceptance tests; demonstration guide; corporate three-client operating model; ADR 0012 and this report.

## 3. Files modified

Runtime composition and API routes, permission map, native fixed-operation bridge, desktop navigation/styles/API types, generated OpenAPI/TypeScript, package scripts, packaged-runtime smoke, native integration test, CI, README and context/contract manifests.

## 4. Migrations

None. The sandbox uses a separate ephemeral SQLite repository with current schema 9. Operational facility configuration, telemetry and ledgers are not edited. Main database safety is tested by comparing configuration and accepted row counts before/after a demo step.

## 5. APIs

GET and POST `/api/v1/demo` require a scoped `system.configure` principal. POST takes a UUID and ordered action; approval additionally requires `dispatch.approve`. Snapshot explicitly labels SIMULATION, ACCELERATED_ISOLATED and ephemeral storage. Successful UUID retries return the saved response; conflicting or out-of-order actions reject. Native access uses fixed operations, bounded responses and a single background rehearsal worker so identity/health/lifecycle remain responsive.

## 6. Events

Existing registry, intelligence, optimization, dispatch, finance, AI and telemetry events/outboxes are reused. Separate hash-chained rehearsal audit records each successful step with the operator identity and request ID. No fake cloud acknowledgement or new command channel is introduced.

## 7. Tests created

Domain chain, explicit human gate, denied approval, excluded critical asset, UUID replay, quality degradation, measured execution/rebound, cited explanation, unconfigured-cloud rejection and host data isolation. Real PostgreSQL HTTP test reconciles received event count and cursor totals after fault injection. React tests require an explicit approval click, preserve retry IDs and block false cloud completion. Native test checks isolated scope and real normal-state generation. Frozen smoke now executes all seven local stages.

## 8. Checks run

Full formatting/lint/types/generated-contract/Python/frontend/build checks; actual PostgreSQL/pgvector with no skipped tests; native formatting/Clippy/tests; canonical CLI acceptance with a disposable PostgreSQL receiver; release package and frozen-runtime smoke; ad-hoc code-signature verification.

## 9. Results

Application checks: 174 Python tests passed with no skips, 39 frontend tests passed, and native suite comprises 3 passing tests: 216 total. Four upstream Python deprecation warnings remain. The final macOS package built successfully; its frozen runtime passed all seven local demonstration stages from a clean temporary directory, and its ad-hoc signature passed deep/strict verification. Final native formatting, Clippy and lifecycle/bridge tests passed. Dependency versions are unchanged from Phase 10; its seven RustSec maintenance/soundness warnings remain documented release-review items.

## 10. Canonical evidence

`.local/phase11-demo.json` records all nine stages, 3,995 ingested telemetry rows, 4,041 total acknowledged domain events, zero pending sync events, a valid audit chain, COMPLETED command, VERIFIED execution/rebound result and cited AI evidence. The run verified 1.84 USD of synthetic net energy value at an explicitly declared 0.15 USD/kWh simulation rate. Execution and rebound each contain 60 complete measured seconds. The scenario remains at elevated demand afterward; a verified event does not imply that ongoing peak risk has disappeared.

## 11. Desktop features

Integrated Demonstration exposes the current virtual clock, demand, risk, next permitted step, proposal/constraint evidence, explicit approval, command state, measured verification, advisory citations, sync status and audit integrity. Evidence can be copied before shutdown. The normal facility's existing operational modules remain available independently.

## 12. Limitations

The sandbox clock is accelerated and paused between actions; it does not demonstrate real human response-time guarantees. Rehearsal records are temporary. Desktop cloud stages need a separately enrolled receiver; without it the UI truthfully stops after local completion. The complete CLI acceptance provisions an actual disposable receiver automatically. Production signing/notarization, non-macOS builds, SSO, unattended edge hosting, remote action delivery and physical OT commissioning remain outside this simulation milestone.

## 13. Simulations/mocks

All factory telemetry and financial amounts are synthetic. Domain services, SQLite ingestion, constraint evaluation, dispatch adapter, verification, audit and HTTP/PostgreSQL persistence are actual implementations. NetworkGate injects an outage around real transport; it does not fabricate responses. The CLI approval flag is explicit authorization for an automated disposable test. Desktop approval is a separate user action.

## 14. Technical debt

Rolling-mean forecasting remains the implemented model; XGBoost/LightGBM need representative data and measured justification. AI explanations are local extractive retrieval, not a trained language model. Enterprise read projections, identity/RLS, unattended edge hosting, mobile field synchronization, remote authorization protocol, retention and deployment controls are specified next-stage work. Existing upstream dependency warnings remain visible.

## 15. Security/safety

No data-quality, hard-constraint or authorization bypass is added to operational services. Demo scope is separate from the authorized host facility and cannot target operational assets. Main transport credentials remain native-only. Explicit approval is permission-checked; no page load or inference triggers it. Demo cloud tokens are separately provisioned; unconfigured/disconnected states cannot claim successful reconciliation. No real-machine or real-savings claim is made.

## 16. Performance/budgets

Each local step advances a bounded number of synthetic seconds. Generated telemetry still passes ordinary validation and outbox persistence. Cloud draining is bounded to 500 iterations, with conflicts/offline results surfaced. Native background work is limited to one demonstration request, with a bounded response and timeout. Real production latency and capacity remain separate measurement requirements; the Phase 10 telemetry benchmark is retained.

## 17. Documentation and client handoff

The Corporate Operating Model describes headquarters, plant and field responsibilities, a daily multi-facility workflow, one-way current sync versus future remote delivery, shared contracts, identity/freshness requirements and build order. The current runtime is a child of desktop; unattended plants require a service host independent of the UI. Web should begin with enterprise identity and cloud read projections; mobile should begin with alerts, asset views and field reports. Remote approvals follow only after the edge revalidation/delivery protocol is implemented and tested.

## 18. Next stage

Desktop SIMULATION is ready as the reference client and domain implementation. Begin shared enterprise foundation and read-only web development in a separately scoped next task; then mobile field workflows. Do not duplicate domain rules in either UI or expose Tauri/OT/database internals to them. Do not equate this milestone with a production-certified industrial release.

## Publication verification — 3 October 2026

Fresh local verification passed: 174 Python tests (zero skips with a temporary compiled
pgvector v0.8.0 library), 39 frontend tests and 3 native tests. The complete platform
check passed formatting, lint, types, generated contracts and UI build. The first run
skipped the unavailable pgvector dependency; the subsequent full Python run exercised
it successfully. Four upstream Python deprecation warnings remain.

The canonical nine-stage PostgreSQL/HTTP demonstration passed again, with 3,995 telemetry
rows, 4,041 acknowledged events, zero pending events, valid audit integrity and 1.84 USD
of explicitly synthetic net energy value. The existing packaged macOS runtime passed
its clean-environment smoke, and the existing bundle passed deep/strict ad-hoc signature
verification. No application code, contract or migration changed in this publication pass.

A portable, identifier-free [acceptance summary](../evidence/phase-11-acceptance.json)
is included for repository readers. README presentation, architecture diagrams, setup
and evidence navigation were refreshed. Hosted CI results and current dependency-scan
status must be checked separately; this pass did not rerun vulnerability audits.
