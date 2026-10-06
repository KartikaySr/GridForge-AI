# Desktop prototype release scope

User direction, 6 October 2026: complete the desktop before starting web/mobile; the product is currently a prototype. Web and mobile remain pending. This scope distinguishes a usable simulation prototype from the broader desktop product specification and production commissioning.

## Prototype acceptance

- Native macOS application with embedded local runtime, authenticated sign-in and role-enforced APIs.
- Deterministic simulator, validated/normalized telemetry, explicit stale/bad/disconnected states, local persistence and recovery.
- Registry and asset constraints, baseline forecast/risk evidence, explainable bounded proposals, human approval, simulated acknowledgement and quality-gated verification.
- Versioned synthetic tariffs and clearly separated estimated/verified simulated financial results.
- Transactional edge-to-cloud synchronization, offline backlog and idempotent reconnection.
- Scoped extractive knowledge/analytics, local security audit and redacted operational diagnostics.
- Immutable production reports and production-normalized comparison gates.
- Persistent demand-risk incidents with investigation notes, source lifecycle, revision-safe acknowledgement/closure and visible processing backlog/failures.
- Command Center demand/forecast/threshold visibility without stale values presented as live.
- One native runtime owner per database on supported POSIX hosts, with ownership released by the OS after a crash.
- Format/lint/type/contract tests, negative authorization and recovery tests, native process tests, packaged-runtime smoke and repeatable synthetic acceptance demonstration.

Prototype screens consolidate related modules: registry covers facilities, lines, assets, devices and mappings; Telemetry covers live/history/quality; Security & Operations and System Health cover audit, users, metrics and worker/component diagnostics. A module's presence does not establish every future feature in the full frontend specification.

## Explicit prototype limits

Only the current macOS architecture has desktop package evidence. POSIX ownership is tested; Windows ownership/distribution remains unsupported until implemented and tested. The desktop owns the runtime: closing it stops collection. This release does not promise unattended factory operation, tray/start-on-login or automatic updates.

Forecasting remains rolling-mean-v1, with existing prospective evaluation. No XGBoost/LightGBM superiority, calibrated probability or real-data accuracy is claimed. Optimization remains bounded curtailment, not general production scheduling, minimum-run/off scheduling or market arbitrage. Utility billing finalization and performance-fee settlement are not simulated into apparent real earnings.

Knowledge ingestion remains plain text with extractive retrieval; PDF/OCR and generative providers are future features. Saved asset workspaces and full asset-detail tab suites remain extensions beyond the consolidated prototype views. Account recovery requires an existing administrator or validated backup; external audit anchoring and automated retention are not delivered.

Reports and incident workflow records are LOCAL_ONLY. The original seven domain streams continue to synchronize; local incident closure does not modify source risk or cloud state. Demand-risk incident coverage does not imply email/push delivery or a general configurable alert-rule engine. Closing a SUPERSEDED source is administrative closure, not evidence of safe demand.

## Distribution and next step

The packaged app is ad-hoc signed for local evaluation. Public signed distribution, updater security, multi-OS certification, physical OT commissioning, trained-model field validation and utility settlement remain external or later product gates. Preserve backups before schema upgrades.

After prototype acceptance, the next engineering stage is the shared cloud user API and read-only web client, then the mobile companion. These must reuse domain contracts and server-enforced scope. No web/mobile implementation or deployment is implied by desktop acceptance.
