# Mobile simulation companion

The Expo client implements provisioned sign-in, facility selection, received asset and risk history, offline text reports, synchronization and account sign-out. Desktop retains dispatch authority. All data is simulation evidence.

## Build and connect

Use Node 22 and npm 10 at the repository root, then run `npm ci`. Set `EXPO_PUBLIC_API_ORIGIN` to the exact HTTPS origin of the deployed portal. This value is public configuration. Tokens and database credentials must never use the EXPO_PUBLIC prefix.

Run `npm run mobile` for development and `npm run mobile:export` to validate Android/iOS JavaScript bundles. A phone needs a reachable HTTPS API with the cloud migrations applied and an enrolled synthetic facility. The web demonstration's loopback address is reachable only on its host. A TLS development proxy can expose the local portal to the phone with controlled access.

The portal provides `/api/v1/mobile/login`, `/me`, `/logout`, `/portfolio`, `/facilities/{edge_id}/events` and `/reports`. Browser cookies and mobile bearer sessions have separate namespaces. Existing web sessions migrate with the `web` client default. Apply `0006_portal.sql` then `0007_mobile.sql` before releasing the updated portal. `PortalService.migrate()` performs both steps for local demos and administrative provisioning. Vercel cold starts deliberately skip migrations. Grant the runtime database login membership in `gridforge_portal_reader` and `gridforge_mobile_writer` so it can enter the restricted transaction roles. Report row-level policies restrict inserts and reads to the authenticated owner.

In `apps/mobile`, run `npx eas-cli@latest build:configure` with the owner's Expo account to select the project's iOS bundle identifier and Android application identifier. Set `EXPO_PUBLIC_API_ORIGIN` in the selected EAS environment before building. The checked-in `eas.json` includes internal preview APK and production profiles. Run `npx eas-cli@latest build --profile preview --platform android` for internal testing, and choose iOS when signing credentials are available. Store submission uses the owner's Apple/Google accounts and app records.

## Offline behavior and evidence

Tokens use SecureStore. Sessions expire after one hour. A valid stored session can reopen cached facilities and its SQLite report queue during a connection outage. Reauthentication requires connectivity. Logout requires server revocation and then removes credentials and visible protected state. Local report rows are partitioned by API origin and user ID. A different user cannot upload or view them through the application. Synthetic text notes are stored in the app's SQLite sandbox, without database encryption. Use device access controls and synthetic data during prototype testing.

Each report retains its original UUID, edge ID and text across retries. The server checks current membership and enabled edge status. Identical replays return the original receipt, and changed payloads with the same ID return 409. Conflicts remain visible for review. A lost response leaves the local item pending so retry can retrieve its existing receipt. Each account queue is limited to 100 records, with explicit cleanup for synchronized copies. Reports are field observations and do not alter production, savings or dispatch records.

Alerts show received risk evidence. Push notifications, photos and store publication remain separate roadmap items.

## Release verification

Automated checks cover scoped requests, cookie/bearer separation, duplicate/conflicting reports, revoked membership and logout. Android/iOS bundle export checks JavaScript packaging. Installed-device acceptance still requires a signed development build. Verify sign-in, screen navigation, keyboard/accessibility, offline save, process restart, reconnect/retry, account switching and expiry on both operating systems. Record device/OS and release commit before distributing to testers.

## Dependency patch policy

The root lockfile pins the tested dependency tree. The targeted `minimatch@>=7 <11` override uses 11.0.8 to address GHSA-g3hv-75wg-m249 in Expo fingerprinting and TypeScript tooling. Node 22 satisfies its runtime requirement. Keep the override until both upstream dependency chains adopt a patched version, and verify linting, Expo exports and native project generation when changing it.
