# Phase 10 — security and operational hardening

Completed for the local SIMULATION prototype on 2026-09-30. Production distribution and infrastructure controls remain explicit release gates. Phase 11 has not started.

## 1. Implemented

Persisted local accounts; first-run administrator setup; eight scoped roles; permission gates across all domain routes; eight-hour sessions; revision-based revocation; logout/restart isolation. Added append-only hash-chained audit, correlation IDs, persisted request metrics and redacted diagnostic bundles. Added verified backup/restore, migration checksums, crash/load regressions, accessibility checks, cross-domain simulation regression and a standalone macOS package. Documented signing, updater and production configuration architecture.

## 2. Files created

`services/security/` and `services/operations/`; migration `0009_hardening.sql`; desktop IdentityGate/Security components and tests; native security permission; release Tauri configuration; packaging/smoke/load scripts; security/recovery/performance/pipeline tests; ADR 0011, operating guide and dependency review.

## 3. Files modified

Runtime middleware/routes, repository migrations, permission catalog, native supervisor/IPC/capabilities, packaged launch paths, desktop navigation/bridge/styles, generated API contracts, existing test composition, dependency lockfiles, CI, scripts and context/contract documentation.

## 4. Migrations

SQLite 8 → 9 adds local_users, local_sessions, security_audit with immutable triggers, runtime_metrics and migration_history. Existing local data was backed up to `.local/backups/edge-before-phase10.db` with a SHA-256 manifest before upgrading. Preserved 42,100 telemetry rows, 42,100 corresponding outbox records and 208 predictions. No default account or fabricated operational data was added. PostgreSQL schema unchanged.

## 5. APIs

Added identity status/bootstrap/login/logout, account list/create/change, paginated audit, metrics, redacted bundle and native lifecycle authorization. Private native transport authentication remains mandatory; domain endpoints additionally require server-resolved user permissions/scope. Generated runtime OpenAPI and TypeScript match.

## 6. Events

Audit links actor, scope, request/correlation UUID, timestamp, outcome and prior digest. Existing domain events and seven synchronization streams remain unchanged. Security audit is local; external immutable anchoring is a deployment extension. Logout remains available when audit integrity/capacity fails closed.

## 7. Tests created

Bootstrap/sign-in/logout/restart, all eight roles, foreign-scope rejection, last-admin protection, password hashing, throttling, session revocation, audit tampering, migration checksums, backup/replay/no-overwrite, abrupt exit/WAL recovery, load reconciliation, and dispatch → verification/finance → advisory analytics → PostgreSQL replay. React checks cover private-content hiding/unmounting and axe labels/ARIA.

## 8. Checks run

`npm run check`, Python integration suite with real PostgreSQL/pgvector, `npm run native:check`, `npm run desktop:package`, frozen-runtime clean-directory smoke, `codesign --verify --deep --strict`, npm/pip/Rust scans and a 2,000-batch load exercise.

## 9. Results

Formatting, lint, TypeScript/Python types, generated contracts and web build passed. Frontend: 37 passed. Native: 3 passed, with Clippy warnings denied. Python: 171 passed with real PostgreSQL/pgvector and no skips (32.86 seconds). Total: 211 passing Python/frontend/native tests. Four upstream Python deprecation warnings remain. npm/Python scans reported zero known vulnerabilities; RustSec reported seven upstream warnings detailed in the dependency review.

## 10. Manual verification

Opened the packaged app and inspected its first-run interface: “Create your local administrator”, labeled username/password controls and SIMULATION boundary. No user account was created. The final frozen runtime passed bootstrap, scoped registry reads, diagnostics, logout denial and graceful shutdown in temporary storage, outside the checkout with a clean environment. Ad-hoc signature verification passed.

## 11. Screens/features

Setup/sign-in gate; session identity/sign-out bar; Security & Operations for account creation, role change, enable/disable, counters, audit inspection and explicit redacted JSON clipboard export. Domain permissions remain server-enforced. Browser preview remains non-operational.

## 12. Limitations

Local identity only; no enterprise SSO/cross-edge federation or password-reset workflow. Keep a second administrator and backups. The macOS artifact is ad-hoc signed, not Developer ID signed/notarized. Windows/Linux builds are unverified. Automatic updates are disabled; this phase delivers their gated architecture. Signing keys/feed, external audit anchoring, centralized tracing, deployment alerts and provider PITR drills require real infrastructure. Seven RustSec warnings remain release-review items.

## 13. Simulations/mocks

All equipment, control, forecasts and savings demonstrations remain synthetic. The pipeline fixture uses complete synthetic measurement windows to isolate finance math. Trusted principals are explicit test composition only; production defaults require sign-in. PostgreSQL, pgvector, native process, SQLite recovery and frozen-runtime tests use actual implementations.

## 14. Technical debt

Audit retention/rotation and external checkpoints; persisted/distributed login throttling; credential recovery/SSO; production signing/updater implementation; OS/assistive-technology matrix; upstream dependency maintenance. Mutations fail closed at 100,000 audit entries, requiring an approved archival procedure. A privileged OS owner can rewrite the entire local database beyond a local hash chain's protection.

## 15. Security/safety

No ML/LLM-to-machine path or real OT writes. Native credentials never enter React. Salted scrypt passwords and server-owned role/scope prevent request spoofing. Sessions expire/revoke; streams stop and native cache clears after authentication loss. Audit corruption blocks mutations while allowing revocation. Bundles omit secrets, environment, document text and query results. Restore never overwrites an active database.

## 16. Performance/budgets

Local benchmark: 10,000 points and matching outbox rows in 17.259 seconds; 579.4 points/second; ingest p50 4.907 ms, p95 10.770 ms, maximum 649.115 ms while native compilation competed for resources. Replay deduplicated five points. Automated regression reconciles 1,000 rows/outbox records with a broad 250 ms p95 ceiling. These are local measurements, not production SLOs.

## 17. Documentation

ADR 0011, Operations and Release guide, Dependency Review, API/Event contracts, README, context index and repository manifest updated. CI includes dependency scanning, load checks, release packaging and frozen-runtime smoke. Production signing/updater/configuration gates are explicit.

## 18. Next phase / approval gate

Phase 11 is the final integrated demonstration: normal factory → demand spike → forecast/risk → constrained proposal → human approval → simulated dispatch/load response → verification/savings/audit and the remaining canonical demonstration requirements. **Stop and obtain user approval before starting Phase 11.**
