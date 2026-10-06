# Phase 12A: local production reporting

Completed 6 October 2026 for the simulation prototype. This closes the production-reporting increment only, not the entire desktop specification or the web/mobile release.

## Delivered

Immutable operator production declarations, measured complete-window electricity and specific energy consumption, comparable-period review, traceable evidence and native report history/JSON copy. The domain service enforces role, scope, closed UTC windows, query bounds and UUID replay. Missing/bad/late/duplicate telemetry withholds energy and SEC. Changes in declared throughput or reject fraction prevent an improvement claim. The service never authorizes dispatch or creates savings-ledger entries.

SQLite migration 10 and recovery validation preserve earlier schema upgrades. Runtime OpenAPI and shared TypeScript types include the new DTOs. The native bridge uses fixed allowlisted routes. See [workflow and limitations](../06-engineering/PRODUCTION_REPORTING.md).

## Verification

- `npm run check`: PASS; formatting, lint, types, generated-contract checks, 42 frontend tests, 182 Python tests and production frontend build.
- PostgreSQL integration includes pgvector v0.8.0 compiled into a temporary test directory. No database integration tests skipped in this run.
- `npm run native:check`: PASS; Rust formatting, clippy and 3 integration tests, including report/history calls through the native bridge.
- `npm run desktop:package`: PASS; macOS application bundles the updated frozen Python runtime.
- Frozen-runtime smoke: PASS from a clean environment and temporary database, including identity, reporting availability and the authorized simulation/verification demonstration.
- Total passing tests: 227. Four dependency deprecation warnings remain in Python test infrastructure; no test failures.

Full regression initially exposed obsolete schema assertions, recovery's schema upper bound and legacy test fixtures retaining the new reports table while pretending to be older databases. These were corrected and the complete suite rerun successfully.

## Boundaries and remaining work

Production output and rejects remain operator declarations; no real equipment, independent quality verification, real savings or causal performance result is claimed. Reports are LOCAL_ONLY and do not join the seven sync streams. The report-copy action exports JSON through the clipboard, not a formatted PDF. Maximum report window is one hour; full billing and long-period aggregation remain future work.

The package is ad-hoc signed, not notarized for public distribution. Only the current macOS environment was verified. Existing user facility data was not opened or migrated by packaging/smoke tests. Back up that data before launching the upgraded application.

The [release scope](RELEASE_SCOPE.md) and [deployment preparation](../06-engineering/DEPLOYMENT_PREPARATION.md) enumerate remaining desktop work, enterprise cloud prerequisites and web/mobile acceptance. No hosted resources or web/mobile applications were deployed in this increment. Private competition material remains excluded from Git.
