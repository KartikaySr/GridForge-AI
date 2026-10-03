# System Architecture

## Topology

OT/Simulator -> Edge Adapters -> Validation/Normalization/Quality -> Local State/Event Layer ->
Forecast/Risk -> Constraints/Optimizer -> Authorization -> Dispatch Adapter -> Verification -> Finance.
Local Desktop UI observes/commands through authenticated local APIs. Durable edge store/outbox synchronizes to
Cloud Core -> FastAPI/Workers -> PostgreSQL/pgvector -> future Web/Mobile.

## Deployment units

Tauri + React/TypeScript shell; minimal Rust native layer; Python/FastAPI local/domain runtime; supervised workers;
SQLite prototype edge store; central PostgreSQL; Redis/broker optional behind abstractions.

## Boundaries

UI does not speak OT. Adapters do not own business policy. Models do not issue commands. Optimizer creates
proposals. Dispatch executes only authorized constraint-valid command envelopes. Finance consumes verified actuals.

## Resilience/versioning

Timeout/retry/circuit/degraded state for dependencies. Bounded telemetry buffers. Idempotent ingestion/sync/commands.
API `/api/v1`; event `schema_version`; ordered DB migrations; immutable model versions; effective-dated policies/tariffs.
