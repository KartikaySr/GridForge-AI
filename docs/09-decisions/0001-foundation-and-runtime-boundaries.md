# ADR 0001: Foundation tooling and runtime boundaries

Status: accepted for Phase 0. Product modules are deferred to their approved phases.

## Decision

Keep npm workspaces and a single root npm lockfile. Pin direct JavaScript dependencies,
Node 22, and npm 10.9.8. Use Python 3.12 with uv 0.12.15, root pyproject.toml and uv.lock.
`apps/api/requirements.txt` is a pointer, not a second dependency authority.
Use Prettier, ESLint, strict TypeScript, Ruff, strict mypy, Vitest and pytest.

The backend remains a modular monolith. `services/` contains future Python domain and
application modules, not separately deployed microservices. Each module owns its policy,
use cases, repository interfaces and tests. Transport handlers delegate to modules as each
product phase replaces the existing scaffold. No broker is selected.

`edge/runtime/` will compose the local FastAPI runtime and supervise local workers.
`apps/api/` will compose the central API. Both may use the same domain modules without
importing one transport entry point from the other. Phase 0's API remains a temporary local
scaffold; this ADR does not claim either deployment architecture is implemented.

SQLite is the prototype edge store; PostgreSQL is the central store. Local storage has a
purpose-built schema. A local transactional outbox is introduced with durable edge records,
with cloud synchronization completed in Phase 8. Ordered central migrations are separate
from ordered edge migrations. Never edit an applied migration to change deployed state.
The current 0001 SQL file is unverified bootstrap SQL, not a migration framework.

FastAPI OpenAPI will generate client contracts. Shared TypeScript contracts currently name
scaffold responses only. They are not canonical future telemetry/event schemas. No fabricated
event implementation or independently maintained second operational model is added here.
Tauri/native and OT implementations remain outside portable packages.

## Consequences

No package-manager migration, repository reshuffle, Rust installation, broker, or domain
schema expansion is necessary for Phase 0. The temporary route-level business stubs and
in-memory state are explicit debt to retire in Phases 2–7. Dependency upgrades must preserve
lockfiles and pass the same checks as CI. Production Python/platform changes require a later ADR.
