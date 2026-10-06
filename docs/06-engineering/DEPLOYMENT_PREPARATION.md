# Deployment preparation

Status: recommended targets, not a deployment approval or a production-readiness certificate. Updated 6 October 2026.

## Accounts and distribution

- GitHub: repository and Actions access; Releases can distribute desktop installers. Keep signing secrets in a protected release environment, never in source control.
- Vercel: future React web deployment. Set the production API origin only after the central user API and tenant isolation exist. The current desktop browser preview is not the enterprise web application.
- Render: shared FastAPI service and managed PostgreSQL with pgvector. Resolve region, recurring budget, network access and backup retention before provisioning. Current cloud code is an enrolled-edge receiver plus restricted AI reporting, not the complete enterprise API.
- Expo/EAS: build and distribute future Android/iOS clients. Prepare an Apple Developer account for TestFlight/App Store and a Google Play developer account for Android distribution. An Expo preview does not establish device/store readiness.
- Desktop signing: macOS needs an appropriate Developer ID certificate and notarization credentials. The current locally built application uses ad-hoc signing. Windows needs its own build/test environment and signing decision. Do not distribute the macOS bundle as a Windows installer.

Use private account settings to provide secrets when implementation reaches deployment; do not paste credentials into chats or commit them. Account setup does not require purchasing every service now.

## Platform responsibilities

Desktop owns plant-local observation, validation, constraints, authorized simulation and evidence. It must keep working through cloud disconnection. The current application stops its child runtime when the UI closes; unattended operation still needs the separately supervised edge-service increment.

Cloud owns durable received events and will own enterprise user identity, membership and scoped read projections. Central PostgreSQL remains the durable central source of truth. Every edge has an enrolled identity and independent durable outbox cursors. An edge enrollment secret must never authenticate a web/mobile user.

Web will expose received multi-facility evidence and its freshness. Mobile will expose scoped field information and idempotent queued observations. Neither client gains a direct equipment, local database or edge-token connection. First release excludes remote dispatch authority.

## Decisions required before staging

1. Select the first release boundary: a three-client simulation MVP or the full original desktop specification before expanding clients.
2. Select supported desktop operating systems and mobile test devices. macOS has local build evidence; additional operating systems need independent evidence.
3. Select API/database region, data retention, restoration objectives, acceptable recurring cost and domain ownership.
4. Define the initial pilot organization/facility enrollment and administrative account provisioning without embedding real tenant IDs in source.
5. Supply representative data and utility semantics before claiming trained-model performance, billing accuracy or industrial savings. The existing synthetic workflow remains labeled SIMULATION.

## Evidence needed for go/no-go

A release commit must pass the source and native checks plus hosted CI. Validate generated contract compatibility, negative authorization and cross-tenant tests, clean-database migrations, backup restoration, lost-network/replay behavior and fresh/stale presentation. Run the installed desktop independently of the checkout and test installed mobile builds. Verify signing and any updater manifests before enabling external distribution. Configure service health, error monitoring and a tested recovery procedure.

The deployment runbook must name environment owners, secret locations, commands/configuration for the implemented release, expected health responses, rollback/recovery procedure and recurring resource limits. No current document asserts that these future deployment gates have passed.
