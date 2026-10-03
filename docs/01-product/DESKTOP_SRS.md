# Desktop Platform SRS

## Mission

GridForge Desktop is the facility-local operational Edge Control Plane. It ingests/normalizes OT telemetry,
maintains trustworthy state, supports local continuity, forecasts demand, detects risk, evaluates flexibility,
generates explainable optimization proposals, coordinates authorized simulated dispatch, verifies outcomes,
attributes value and synchronizes auditable records.

## Personas

Plant operator; energy manager; OT/controls engineer; reliability engineer; administrator; analyst; read-only executive.

## 30 modules

Command Center; Facilities; Production Lines; Assets; Live Telemetry; Telemetry Explorer; Data Quality;
OT Devices; Signal Mapping; Energy; Tariffs; Forecasting; Risk; Flexibility/Constraints; Optimization;
Dispatch Control; Verification; Savings/Arbitrage; Alerts/Incidents; AI Copilot; Knowledge; Reports;
Integrations; Sync Center; Jobs/Workers; System Health; Audit/Security; Users/RBAC; Simulator; Settings/Diagnostics.

## Required workflows

Startup: shell -> local runtime -> local DB -> auth/config -> edge identity -> connectors -> last known state ->
live subscriptions, with degraded states visible.
Telemetry: connector -> validation/quality -> normalization -> local ingestion -> aggregate/state -> persistence/
buffer -> live event -> features -> sync.
Optimization: forecast/risk/manual trigger -> policy -> candidates -> hard constraints -> scoring/solve ->
proposal/explanation -> authorization -> dispatch state machine -> verification -> finance.
Offline: cloud loss must not stop permitted local telemetry/state; queue sync-safe records; block cloud-dependent
authority; reconnect with ordered/idempotent reconciliation.

## Non-functional

No stale value masquerades as live. Explicit units/timezone/quality. Durable command state survives restart.
Bounded queues/backpressure. Accessible keyboard/focus/contrast. Fixed precision money. Observable failures.
No physical actuation in prototype.
