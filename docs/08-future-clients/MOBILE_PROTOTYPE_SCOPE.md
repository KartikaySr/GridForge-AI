# Mobile prototype scope

Authorized 19 October 2026. Mobile is the field companion in the shared GridForge repository. Default is simulation; no OT writes or remote dispatch approval.

## Acceptance

- Native React Native/Expo client with simulation labels and accessible facility, asset, risk-alert and field-report views.
- Central user identity and facility membership enforced on every request; dedicated mobile session transport, revocation and secure device token storage. Never reuse edge tokens.
- Read APIs reuse versioned portal/domain evidence contracts. Receipt age must remain distinct from plant health.
- Offline text reports persist locally with immutable request IDs and user/facility ownership. Retry preserves identity and body. Central writes enforce scope and reject conflicting replays. Offline pending is not uploaded or acknowledged.
- Account changes cannot upload another user's pending reports. Logout clears credentials and protected views.
- Automated scope, expiry, duplicate/conflict and network-retry tests; native build and actual device/simulator acceptance recorded separately.

## Implementation boundaries

Photos, push delivery infrastructure, equipment control, offline approvals and store publication are separate increments. Alerts initially show received risk evidence; no claim of background push delivery. Reports are field observations, not verified production or savings data.

## Environment gate

Current Mac has Xcode Command Line Tools only; `simctl` unavailable. Android `adb` unavailable. Source/type/logic validation cannot substitute for installed iOS and Android acceptance.

Status: frontend modules, bearer session transport, scoped report API, migration 0007 and persistent offline queue are implemented. See [deployment and verification](../06-engineering/MOBILE_DEPLOYMENT.md). Installed-device acceptance and signing remain release gates.
