# Phase 10 operating and release guide

This release is a **single-facility SIMULATION desktop**, with optional explicitly configured cloud replication. It has no physical OT write adapter. Local users do not confer organization-wide cloud authority.

## First run and identity

Open the desktop and create the first local administrator (unique username, password of 12–128 characters). No default password is shipped. Credentials are salted and hashed with scrypt (N=131072, r=8, p=1); passwords are never persisted in renderer preferences or diagnostic bundles. The server resolves permissions from persisted accounts. A renderer-supplied role, tenant or facility never provisions authority.

Eight roles are defined in `services/security/policy.py`. SUPER_ADMIN and ORG_ADMIN administer this local installation; FACILITY_MANAGER operates it without account administration; ENERGY_MANAGER handles planning, approvals and finance; OPERATOR requests/cancels dispatch; OT_ENGINEER configures simulated assets/devices and telemetry; ANALYST inspects advisory analytics/audit; VIEWER reads operational data. Every capability is constrained to the edge's persisted organization and facility. Domain services independently enforce approval, cancellation, finance, AI and synchronization permissions.

Sessions last at most eight hours. Logout, disabling an account, role revision and runtime restart revoke access. The last enabled administrator cannot be removed. The native pipe credential authenticates the desktop process separately from the human account. Health/basic redacted diagnostics remain available to the native supervisor before sign-in for recovery. Domain data requires user authentication. Simulator ingestion continues while users are signed out.

Five login attempts per minute are permitted per runtime. This is a local rate limiter; restarting the process resets it. Password-reset and federated SSO/OIDC are not implemented. Keep a second administrator for recovery; if all credentials are lost, use an authorized encrypted backup or separately engineered recovery procedure. Do not edit user tables to bypass access controls.

## Audit, observability and diagnostics

Schema 9 adds users, revocable sessions, append-only security audit, request metrics and migration checksums. Audit entries link actor, request ID, correlation ID, outcome and scope with SHA-256 chaining. Triggers reject updates/deletes. Startup and audit inspection verify the chain; detected corruption blocks mutations. Existing domain events retain proposal, approval, dispatch, verification, finance and AI evidence.

HTTP responses carry `X-Request-ID` and `X-Trace-ID`; a valid domain request UUID becomes the correlation ID. Bounded permission labels keep metric cardinality independent of arbitrary URLs. Security & Operations displays persisted request counts, durations, counters and audit integrity, and lets authorized users copy a redacted JSON diagnostic bundle. It includes no environment, credentials, document text or SQL results. Clipboard export is explicit; storing or sharing it is the operator's choice.

The audit chain is tamper-evident against ordinary row alteration, not a proof against a privileged owner rewriting/truncating the entire database and chain. External signed checkpoints/WORM retention and centralized OpenTelemetry export remain deployment extensions. Security audit is local; the existing seven domain outbox streams replicate their own events. At 100,000 audit entries mutations fail closed: archive the complete installation under a separately approved retention/rotation procedure; automatic deletion is intentionally absent.

## Backup, restore and crash recovery

Run these commands from the repository or an approved maintenance environment:

```sh
uv run python -m services.operations.recovery backup .local/edge.db .local/backups/edge-snapshot.db
uv run python -m services.operations.recovery validate .local/backups/edge-snapshot.db
uv run python -m services.operations.recovery restore .local/backups/edge-snapshot.db .local/restored/edge.db
```

Backup uses SQLite's online backup API, including committed WAL data. Files are created exclusively with owner-only access. The companion manifest records SHA-256, schema, identity and audit head. Validation checks SQLite integrity, foreign keys and the audit chain. Restore refuses existing destinations and verifies the manifest before creating a new database; it never overwrites a running installation.

Stop the desktop before an operator changes which database is active. Retain the original database and WAL together until restore verification succeeds. Test replay/duplicate suppression after recovery. Restoring an older cloud-synchronized copy may expose cursor/sequence divergence; sync must stop on conflict rather than overwrite cloud truth. Do not clone the same edge identity into two active writers. Target backup frequency is an operator decision; no RPO/RTO is promised by this prototype. Store backups on encrypted, access-controlled media and verify restoration periodically. PostgreSQL deployment backups require provider PITR/WAL retention and a restore drill independent of the local backup tool.

## Packaging

```sh
npm run desktop:package
```

PyInstaller builds an isolated runtime under `packaging/runtime`; Tauri includes it in a release macOS `.app`. The runtime uses the same private stdin handshake and fixed loopback API as development. Packaged data lives in the OS application data directory for `com.gridforge.desktop`, separately from `.local/edge.db`. A packaged first run therefore requires its own administrator setup. The development command remains `npm run desktop:native`.

`tauri.release.conf.json` uses an ad-hoc signature for local simulation testing. It is **not Developer ID signed or notarized for distribution**. Only the current macOS architecture is built here. Windows and Linux packaging need platform-specific build hosts, signing and smoke checks before release.

## Signing and update architecture

Production release must be an isolated CI job with protected environment approval. Build from reviewed lockfiles; run tests, dependency scans, migration/restore and frozen-runtime smoke checks; generate artifact hashes/SBOM; sign all nested binaries and frameworks, then the outer app with a protected Developer ID key; notarize with Apple and staple the result. Validate with `codesign --verify --deep --strict` and Gatekeeper on a clean host. Store credentials in the release environment/keychain, never the repository or diagnostic bundle. An ad-hoc bundle is not publishable.

Automatic updates are **disabled**; no updater plugin, feed or public key is active. The proposed update architecture uses Tauri's signed update artifacts, an HTTPS allowlisted feed, a pinned public key and a protected private signing key separate from Apple signing. Manifest targets must match OS/architecture/channel and enforce monotonic versions. Reject unsigned, mismatched, downgraded or expired releases. Installation requires an explicit user action, no pending approved simulator command, a verified backup and migration preflight. Preserve the last working signed version and restore the matching backup on schema-incompatible rollback. Key rotation requires a trusted signed release containing the next key before retiring the old one. Implementing/enabling this transport requires real release infrastructure and acceptance tests; this phase delivers the gated architecture, not a fake update endpoint.

## Production configuration

Runtime defaults remain local simulation. Native composition forwards only explicitly allowlisted cloud/AI configuration. Provision edge enrollment credentials and database roles outside source control. Cloud URLs require HTTPS except loopback development. Use PostgreSQL roles with least privilege, TLS, secret rotation and organization/facility scope; AI analytics uses the SELECT-only allowlisted-view role and knowledge retrieval uses scoped policies. Never reuse a superuser DSN in a production process.

Deployment acceptance additionally needs tenant enrollment/identity federation, backup retention, disk/metric alerts, external audit anchoring, incident ownership and site-specific operational engineering. The local prototype does not certify those external controls.

## Repeatable checks

- `npm run check`: format, lint, types, generated contracts, Python/frontend tests and web build.
- `npm run native:check`: Rust formatting, Clippy and real process/lifecycle tests.
- `npm run security:scan`: npm, Python and Rust advisory databases (install `cargo-audit` in CI).
- `uv run python -m scripts.telemetry_load --batches 2000`: isolated durable telemetry benchmark with row/outbox reconciliation and replay check.
- `npm run desktop:package`: standalone simulation app; run its bundled runtime from a temporary working directory to verify source independence.

Accessibility checks cover labeled authentication controls, names/ARIA, keyboard focus, skip navigation and semantic status messages. Automated DOM checks do not replace assistive-technology testing on each supported OS.

## Prototype runtime ownership

The native runtime acquires an exclusive process-lifetime lock beside its database before startup. A second native runtime targeting the same resolved database path fails closed. On POSIX hosts the kernel releases ownership when the process exits, including a crash; the lock file remains and must not be deleted while any runtime is running. This prevents two simulator owners, not all administrative access: offline repair/backup tooling still requires the documented maintenance procedure. Independent databases and ephemeral in-memory demonstrations can run separately.

The ownership implementation currently supports POSIX hosts. Windows needs its own tested locking implementation before claiming Windows desktop support. The current release remains a macOS local prototype. Closing the UI stops its runtime; database ownership is not an unattended-service implementation.
