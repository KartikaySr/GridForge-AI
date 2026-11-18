# Three-platform simulation demonstration

Run `npm run demo:triangle` from the repository root with the pinned Node/npm/Python/Rust tools and local PostgreSQL binaries available. Close other development servers occupying ports 5173, 5174 and 8082 first. The launcher starts a temporary PostgreSQL instance, authenticated synchronization receiver, web server, native desktop and portal API. First-time native compilation takes longer than subsequent starts.

The command opts into the canonical simulated approval/dispatch rehearsal. It prepares one isolated factory with five synthetic assets, historical normal/bad/peak telemetry, forecasts, risk and incident history, constrained proposals, approved simulated dispatch, verification and synthetic savings, advisory audit, two production reports and a field observation. Recent normal telemetry fills the five-minute forecast window before native startup. Once desktop starts, its simulator continues at 1 Hz and its durable outbox sends updates to the shared cloud.

Each run writes a new private `.local/triangle-<UUID>/edge.db` and owner-readable `login.json`. The login file contains the desktop username, unique web/mobile username, password and common edge/facility identifiers. Read it privately before recording. The desktop development supervisor uses `GRIDFORGE_DEMO_ID` to select this isolated database. Regular desktop startup retains its usual database. Desktop and cloud credentials use independent authentication stores, with the same generated password for this rehearsal.

## Presentation order

1. Desktop — sign in, open telemetry and show five changing asset readings. Show Forecasting & Risk, then proposal, dispatch and verification history. The seeded approval is an explicitly authorized historical rehearsal. New proposals still require operator approval. Production reports and incidents remain local desktop evidence.
2. Web — open `http://127.0.0.1:5174`, sign in with the portal username, select the common facility, and enable five-second auto-refresh. Show telemetry receipt updates, historical risk/proposals, dispatch, finance and advisory evidence. Older-record pagination disables auto-refresh so the page remains stable.
3. Mobile — point `EXPO_PUBLIC_API_ORIGIN` at a reachable HTTPS portal and start the Expo client. Use the same portal account, select the common edge, inspect assets and risk, then load synchronized report history. Save a new synthetic field observation. Disconnect, save another, reconnect, and synchronize. Web → Field reports → Refresh newest shows that account's uploaded observations. Repeating synchronization preserves request identities and does not create duplicate records.

The local portal binds loopback. A physical phone requires a controlled HTTPS tunnel/proxy to port 8082, or the deployed HTTPS portal described below. A server bundle export does not verify phone networking or device installation.

## When the platform is hosted

Set `GRIDFORGE_CLOUD_DATABASE_URL` privately to an administrative setup connection for the same managed PostgreSQL database used by the hosted portal, then run `npm run demo:triangle -- --use-configured-cloud`. This explicitly creates a new simulation facility and user in that database. Hosted web and mobile can read that facility while the desktop simulator runs locally. The hosted portal needs migrations through 0007 and the configured database roles. Its web origin must match the deployed HTTPS domain.

Each hosted rehearsal uses separate scope identifiers and a unique account. Hosted demo records remain after the launcher exits. Keep those accounts limited to demonstration use and revoke them through administrative tooling when retired. Stopping the launcher stops its owned child processes and local receiver. Hosted data becomes historical after the desktop stops sending it. Continuous unattended hosted simulation would require a separately operated long-running edge worker, because the current native runtime follows desktop lifecycle.

## Verification and boundaries

The integration test exercises the actual preparation code, checks every synchronized evidence stream, reopens the seeded SQLite database in the native telemetry runtime, confirms newly generated samples reach PostgreSQL, and verifies an idempotent mobile report appears identically through web and mobile APIs. It also checks private credential-file permissions and inaccessible-facility rejection. Native and installed-phone UI acceptance remain separate checks. All production, dispatch and savings evidence in this walkthrough is synthetic.

## Local rehearsal evidence — 18 November 2026

Launched the native desktop and web/portal together. An authenticated portal check confirmed matching factory IDs, 15 new telemetry records over three seconds, populated telemetry/registry/intelligence/optimization/dispatch/finance/AI streams, and a received field report. Native lifecycle checks passed. This run validates desktop-generated samples reaching cloud reads. Installed-phone acceptance and a deployed HTTPS origin remain required for a physical three-device demonstration.
