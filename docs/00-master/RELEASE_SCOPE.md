# GridForge three-client release scope

Updated 6 October 2026. User-authorized order: finish desktop gaps, build shared cloud/web, build mobile, prepare deployment. This document supersedes any implication that Phase 11 completed the original full product specification. Phase 11 completed a tested simulation workflow only. No later phase is complete merely because its pages render.

## Deployment recommendation

Desktop installers: GitHub Releases, built per target OS with Tauri. macOS is locally verified; Windows/Linux require their own build/test evidence. Production macOS distribution requires Developer ID signing/notarization; Windows distribution needs its own signing decision. Signing secrets never enter Git.

Web: React/Vite on Vercel. Shared cloud: FastAPI on Render with managed PostgreSQL/pgvector. Mobile: React Native/Expo, EAS builds and TestFlight/App Store/Google Play distribution. These are recommended targets, not provisioned resources. Accounts, budget, DNS, region/data residency, backup retention and signing credentials must be resolved before deployment. Do not create paid resources without authorization.

Official deployment references checked 6 October 2026:

- https://tauri.app/distribute/
- https://vercel.com/docs/frameworks/frontend/vite
- https://render.com/docs/deploy-fastapi
- https://render.com/docs/postgresql-extensions
- https://docs.expo.dev/deploy/submit-to-app-stores/

## Desktop scope and acceptance

Completed reference: local simulation telemetry, registry, baseline forecasting, restricted curtailment proposals, human approval, simulated dispatch, measured synthetic finance, scoped local identity, audit and durable edge-to-cloud sync.

Desktop increments (Phase 12A closes item 1 for local simulation; the rest remain pending):

1. Production records and energy reports: immutable records with product/output/rejects, complete measured intervals, evidence digests, comparable-period SEC calculation, no quality/throughput-loss benefit claim, read/write permissions and native UI/export. Reports must distinguish local-only evidence from synced history.
2. Operational workflows: persistent alerts with acknowledge/resolve semantics, reports/history/export, integration health and bounded worker/job inspection. Acknowledging an incident cannot authorize dispatch.
3. Command Center and asset views: actual/forecast/threshold overlays, linked proposal/verification evidence, asset history, filters and saved views; no placeholder values.
4. Edge lifecycle: separately supervised background service and secure desktop attach, single database ownership, authenticated shutdown/upgrade, restart recovery, optional login startup/tray and notifications. Closing the UI must demonstrably leave an intentionally enabled service running.
5. Forecasting/optimization: representative data, chronological holdout, documented baseline comparison; adopt trained models only with measured justification. Operating-state history and minimum-run/off constraints precede scheduling/shifting; do not claim global optimization from the restricted allocator.
6. Finance: billing-period demand evidence, tariff normalization and finalized/fee eligibility rules. Requires actual agreed utility semantics; synthetic tests cannot establish utility settlement.
7. Knowledge: PDF text extraction and bounded corpus lifecycle; OCR and generative providers only with configured dependencies, evidence and access controls.
8. Security/release: account recovery, audit archival/anchoring strategy, signed distribution/update verification, OS matrix and sustained reliability. Credentials, privileged commissioning and external validation remain external gates.

Acceptance: domain/API tests, negative authorization and stale-input tests, generated contracts, UI interaction checks, native bridge checks, full simulation regression, packaged smoke and honest limitations. Real OT writes remain excluded.

## Phase 12A: production reporting (complete for simulation)

See [acceptance and limitations](PHASE_12A_COMPLETION_REPORT.md). Domain service, native desktop page and versioned API for manually recorded simulation production intervals, immutable quality-gated electricity reports and like-for-like comparisons. Migration 10, generated API contracts and permission catalog affected. No physical control or changes to dispatch authority. No automatic report-to-savings-ledger conversion. Production records are operator declarations, not sensor proof of product quality. Bounded report windows keep processing predictable. Integration with the central reporting model is a later explicit contract increment.

## Shared cloud foundation (pending)

Central identity/session revocation, organization membership, facility authorization, RLS tests with two tenants; read projections over received events with observed/synced timestamps; rate limits and bounded queries; migrations, health endpoints, backup/restore rehearsal and deployment configuration. An edge credential is never a user credential. Current receiver endpoints alone are insufficient for enterprise clients.

## Web release (pending)

Portfolio/facility summaries, assets, received telemetry/history, risk/proposal/verification evidence, sync freshness and scoped audit. Read-only first. No browser-to-edge/database/OT calls. Acceptance: two-tenant isolation, expired/revoked sessions, offline/stale behavior, accessible flows and production build against the deployed API.

## Mobile release (pending)

Android/iOS field companion with authentication, facility/asset summaries, alerts and idempotent offline text reports. Attachments follow bounded authenticated storage and retention. No offline dispatch approval. Acceptance: actual device builds, secure session storage, logout/revocation, network transition/retry tests, duplicate/conflict handling and store signing. Expo preview alone is not an installed-app release.

## Deployment gate (pending)

All chosen client scopes implemented and tested; compatible API versions; hosted CI passing for release commit; isolated staging deployment; secret provisioning; backup restoration; client signing; migration rollback/recovery procedures; monitoring, costs and release runbook. No promise that external store review or industrial certification finishes in one coding session.

## Publication boundary

Publish source, shared contracts, tests, implementation reports and deploy templates. Keep `.local`, secrets, databases, credentials, build caches and `docs/submission` private. No new competition material is to be pushed.
