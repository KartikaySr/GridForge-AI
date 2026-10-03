# Phase 7 completion report — verification and simulation finance

Date: 2026-09-29. Scope: completed synthetic commands, declared tariff assumptions and
quality-gated simulated energy-value accounting. Phase 8 has not begun.

## 1. Implemented

Immutable simulation tariff versions; a pre-dispatch forecast baseline; execution and rebound
verification windows; expected versus measured kW reduction; time-band energy comparison;
separate estimated and verified ledger entries; explicit incomplete demand-charge assessment;
provenance, local audit outbox and financial desktop views.

## 2. Files created

`services/finance/{__init__,contracts,engine,service}.py`, migration `0006_finance.sql`,
`tests/unit/test_finance.py`, `apps/desktop/src/pages/Finance.tsx` and its tests, ADR 0008,
native generated `finance_request` capability and this report.

## 3. Files modified

Repository migration runner; local runtime composition, worker and API; provisioned simulation
permissions; native supervisor/command/capability; desktop navigation and bridge; generated
OpenAPI/TypeScript types; historical migration tests; README, development, API/event contracts,
context index and manifest. `apps/api/app/main.py` remains an unmounted legacy scaffold.

## 4. Migrations

SQLite v5→v6 creates `finance_tariffs`, `finance_verifications`, `finance_ledger` and
`finance_outbox`, with unique request/command keys and JSON/status checks. Local database upgrade
preserved **42,100 telemetry records** and one optimization run. Pre-upgrade SQLite backup:
`/private/tmp/gridforge-before-phase7.db`. Older v1–v4 migration tests were updated to prove
forward upgrades to v6 without losing existing records.

## 5. APIs

Authenticated GET `/api/v1/finance`, POST `/api/v1/finance/tariffs`, POST
`/api/v1/finance/verifications`, GET `/api/v1/finance/events?after=N`. Native bridge accepts only
fixed read/tariff/verify operations. Strict versioned contracts and generated client types are
shared with future clients.

## 6. Events

TariffVersionCreated, VerificationStarted, SavingsEstimated, SavingsVerified,
VerificationCompleted and VerificationIncomplete. Version-1 events carry UTC time, actor,
facility scope, resource/correlation/causation IDs and idempotency key. Events, ledger and
verification status commit atomically; cloud acknowledgement belongs to Phase 8.

## 7. Tests created

Five finance Python tests cover a completed simulated command, replay/conflict, exact execution
and rebound arithmetic, higher-priced rebound loss, estimate/verified separation, no demand-charge claim, incomplete
telemetry fail-closed, tariff band validation, authenticated/strict API and permission denial.
Two frontend tests cover preview and empty verification. Native integration reads finance and
rejects route injection.

## 8. Tests/checks run

`npm run check` ran formatting, ESLint/Ruff, TypeScript/strict mypy, generated-contract
consistency, frontend/Python tests and production frontend build. `npm run native:check` ran
rustfmt, warning-free Clippy and Rust tests. `npm run desktop:build` validates the embedded
native build. Focused finance and migration tests ran during implementation.

## 9. Results

Final suite: 113 Python, 29 frontend and three native tests passed (145 total). Two existing
upstream Starlette/httpx/AnyIO deprecation warnings remain non-failing. No remote CI result is
claimed.

## 10. Manual verification

The actual local v5 database upgraded to v6 and retained its prior telemetry and optimization
records. The finance API and calculation path were exercised with the real local SQLite store in
automated tests. No production utility bill, actual OT system or manual financial UI case was
used to claim real savings.

## 11. Screens/features

Energy & Tariffs creates and lists user-entered simulation versions with explicit currency,
flat energy rate and optional recorded demand rate. Verification & Savings selects a completed
command and version, displays pending/verified/incomplete cases, window coverage, forecast and
proposal links, demand-charge status, and separate estimated/verified ledger entries. Browser
preview cannot make finance requests.

## 12. Limitations

The baseline is a flat forecast, not a rigorous causal counterfactual. Verification requires
complete one-second synthetic telemetry, so missing data produces INCOMPLETE. Demand-charge
value stays INCOMPLETE pending complete billing-period demand and utility-specific rules. There
is no settlement, fee, finalization, physical meter or real-world savings claim.

## 13. Simulations/mocks

Tariffs are user-entered simulation assumptions. The approved Phase 6 command affects only the
simulator. Finance tests use controlled synthetic execution/rebound observations to prove the
formula and deliberately missing observations to prove rejection. UI tests mock the native
bridge; Python/native tests exercise the actual local service.

## 14. Technical debt

Phase 8 cloud sync/ACK, PostgreSQL central truth, production identity/RBAC, utility tariff
ingestion and billing-period demand reconstruction remain future work. A site-specific causal
baseline, settlement rules, meter certification, performance-fee eligibility and real OT
commissioning are outside this prototype.

## 15. Security/safety

Server-owned facility scope, fixed capabilities and session expiry are checked for finance
reads/writes. Strict request bodies reject role/scope injection. Only completed simulator
commands may be verified; no finance operation can authorize or write to OT. A verified energy
ledger requires complete good, timely, mapping-consistent observations and tariff coverage.
Mutations are transactional and request-ID idempotent.

## 16. Performance

The finance worker polls every five seconds and evaluates at most 20 pending cases per cycle.
Tariffs and cases have fixed capacities (100 and 500); API snapshots bound cases to 20 and
ledger entries to 100. Verification processes at most 600 execution seconds plus an equal
rebound for current command bounds. No full load/soak or production throughput benchmark was
performed.

## 17. Documentation

README, development walkthrough, context index, ADR 0008, API/event contracts, manifest and
this report were updated. Financial safeguards follow the architecture requirements in
`docs/04-data-ai/ML_OPTIMIZATION_FINANCE_AI.md`. Demand-charge deferral is supported by
[US DOE](https://www.energy.gov/sites/prod/files/2013/11/f4/standby_rates.pdf) and
[NREL](https://www.nrel.gov/docs/fy17osti/69016.pdf).

## 18. Next phase / approval gate

Phase 8 is edge/cloud synchronization: identity, durable outbox upload, idempotent cursors,
acknowledgement, reconnect and conflict handling. **Awaiting explicit approval before starting
Phase 8.**
