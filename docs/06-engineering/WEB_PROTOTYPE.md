# Web simulation prototype

The browser is a read-only enterprise client. It uses a separate cookie session and facility membership; edge transport credentials never serve as browser credentials. PostgreSQL row-level security restricts reads. Desktop remains the simulated operational control plane. Mobile requires separate user approval.

## Local startup

Use the repository's pinned Node, Python and Rust tooling. PostgreSQL `initdb` and `pg_ctl` must be on PATH for the disposable web demonstration.

Run `npm run portal:demo` in one terminal and `npm run web` in another. Open http://127.0.0.1:5174. The demo executes the actual isolated domain chain, synchronizes to a temporary PostgreSQL receiver and writes private login credentials to `.local/web-demo-login.json` with owner-only permissions. Do not publish this file. Stopping the demo removes its temporary database and credentials. Existing credential files are never overwritten or removed by a second failed launcher.

## Modules

Authorized facility portfolio; received telemetry history; asset/configuration history; forecast intervals and risk evidence; proposal history; dispatch transitions; verification and synthetic savings; advisory event audit. Each view shows source and receipt times with bounded pagination. Recent cloud receipt is not proof of current plant health. Source evidence is historical, and the UI explicitly labels simulation and read-only access.

Optimization and finance event schema 2 carries compact domain evidence. Existing schema 1 events remain immutable reference-only records and cannot be used to invent amounts. Decimal amounts remain serialized strings. Upgrade the cloud receiver before an edge emits schema 2 events. No new database migration is needed for these JSON event bodies. Portal identity and RLS use migration 0006.

## Deployment requirements

Serve the browser and `/api` from one HTTPS origin through a reverse proxy. Configure `GRIDFORGE_CLOUD_DATABASE_URL` and `GRIDFORGE_WEB_ORIGIN` privately for the portal. Provision memberships with `scripts.provision_portal`; there is no public signup. Use secure cookies outside loopback. Apply migrations with an administrator role; grant the runtime the required restricted roles rather than exposing database credentials to the browser. Backups and staging restore checks must precede hosted release.

## Prototype boundaries

No browser dispatch or approvals. Local incident workflow and production reports are not synchronized. No industrial savings claim, real OT control, utility settlement, mobile implementation, or hosted production readiness. Browser verification evidence is recorded below; hosted acceptance remains a deployment gate.

## Browser verification — 19 October 2026

Confirmed on the local synthetic PostgreSQL demo: corrected ProposalCreated evidence displays reduction, threshold and forecast values; logout returns to sign-in; Tab moves username focus to password and Enter submits sign-in. The 390 × 844 viewport reports no horizontal document overflow. All seven modules were exercised in the earlier browser pass, including financial estimated/verified amounts and stale receipt labeling. The proposal lookup defect found there is now corrected and covered by the demonstration regression test.

The web remains a read-only simulation evidence workspace. Authentication expiry/revocation and tenant isolation have backend integration coverage; exhaustive multi-browser and real-device certification are not claimed. Hosted deployment is separate. Mobile development is not authorized yet.
