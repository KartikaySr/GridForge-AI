# Phase 12B: desktop prototype operational closeout

6 October 2026. Implements demand-risk incidents, the live demand overview and single-runtime database ownership. This is a local simulation prototype milestone, not completion of every feature in the full desktop product specification. Web/mobile remain unimplemented.

## Delivered

Persistent demand-risk incidents consume real domain events with an atomic cursor and replay-safe recovery. Server-enforced acknowledge/close actions retain revision, identity and investigation notes. Active risk cannot be closed; superseded evidence stays explicitly superseded. Failures and pending events are visible. SQLite schema 11, shared generated contracts and fixed native routes support the workflow. Records remain local-only.

Command Center now shows quality/freshness-gated load, baseline forecast peak, threshold/headroom and risk, plus an actual/forecast/threshold chart. Invalid or stale inputs withhold numeric results. Obsolete hardcoded synchronization labels now use runtime state. No fabricated savings, model accuracy or physical control status is introduced.

Native startup holds an exclusive database lease on POSIX hosts. Duplicate native owners fail; kernel locks release after process death. Shutdown waits for in-flight incident processing before repository closure. Windows locking is explicitly unsupported until implemented/tested. UI closure still stops the child runtime.

## Verification

- Full source checks passed: formatting, lint, types, generated contracts, frontend build, 188 Python tests and 45 frontend tests.
- Native checks passed: Rust formatting, clippy and 3 process/bridge tests, including incident reads and lifecycle recovery.
- Total: 236 passing tests. PostgreSQL and temporary pgvector integration ran without skipped tests. Four dependency deprecation warnings remain.
- Ownership tests cover duplicate-process rejection, abrupt-exit release and independent database operation.
- Incident tests cover persistence, replay conflicts, transactional rollback, source gating, superseded evidence, permissions/scope/expiry, secure API and cursor validation.
- UI tests cover stale-demand suppression, non-operational browser preview and read-only/error incident states.

The final macOS bundle and clean-environment frozen-runtime smoke both passed, including incident/report endpoints and the authorized simulation demonstration. Results are recorded in [acceptance evidence](../evidence/phase-12b-acceptance.json). Existing user databases were not opened/migrated by these tests. Stop older runtimes and make a backup before launching the upgraded package.

## Scope and next stage

[Desktop prototype scope](DESKTOP_PROTOTYPE_SCOPE.md) documents supported workflows and explicit deferred features. The general alert-rule engine, push notifications, unattended background hosting, saved asset workspaces, trained industrial ML, billing finalization, PDF/OCR and signed multi-OS distribution remain product extensions. No real equipment, utility settlement or production-readiness certification is claimed.

Desktop remains first. The next platform stage is shared enterprise cloud identity/read projections and web, followed by mobile; no client may bypass the existing authority chain. Source, tests, contracts and engineering docs are publishable. Submission materials, databases, lock artifacts and credentials remain excluded.
