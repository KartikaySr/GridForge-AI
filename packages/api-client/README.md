# API client contracts

Local runtime and cloud receiver types are generated from their Python FastAPI OpenAPI documents.
`index.ts` exposes portable API response types; it contains no Tauri imports or credentials.
Native transport and lifecycle DTOs stay in apps/desktop. No generic HTTP proxy is exposed.

Run `npm run contracts:generate` from the root after changing runtime or cloud Pydantic contracts.
Python tests compare the executable OpenAPI shapes with runtime.openapi.json; `npm run
contracts:check` verifies generated TypeScript without rewriting files. The generator uses
its own TypeScript 5 dependency because its peer range does not yet include the app's TS 6.

The older packages/contracts interfaces still describe Phase 0 fixtures. They are not the
canonical telemetry, dispatch or finance contracts; those arrive in their approved phases.
