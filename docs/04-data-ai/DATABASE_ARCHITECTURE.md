# Database Architecture

## Central PostgreSQL domains

iam: users, roles, permissions, memberships, sessions/token metadata.
org: organizations, facilities, production_lines.
asset: types, registry, constraints, maintenance/restrictions.
telemetry: devices, signal_mappings, logs, aggregates, ingestion_batches, quality_events.
energy: utilities, tariff_plans/schedules, market_prices, contracts.
ml: model_registry/versions, features, training_runs, predictions, drift.
risk: risk_events/evidence.
optimization: policies, runs, candidates, constraint_results, proposals.
dispatch: commands, approvals, events, acknowledgements, verification.
finance: baselines, savings, arbitrage_events, fee_rules, snapshots.
alerting: rules, alerts, acknowledgements, channels/deliveries.
ai: documents, chunks/embeddings, conversations/messages/query_runs/feedback.
reporting: definitions/schedules/runs.
integration: integrations/sync_runs/webhooks.
security: audit_logs/security_events.
system: feature_flags/config_versions/service_health/jobs.

## Rules

Benchmark telemetry partition/retention; index facility/time and asset/time. Raw vs aggregate distinct. pgvector
only for semantic content. FKs/checks/unique idempotency keys; NUMERIC currency; explicit units; effective dating.
RLS tenant/facility scope. AI role SELECT-only on allowlisted views and no secrets/auth tables.
Local edge schema is purpose-built, not a full central clone.
