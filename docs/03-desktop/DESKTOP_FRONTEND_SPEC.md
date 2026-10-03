# Desktop Frontend Specification

## Shell

Persistent left nav + top command bar + facility/environment + search/command palette + alerts + edge/cloud/sync
state + user. Dense industrial mission-control, not a generic CRUD admin.

## Navigation

Command Center.
Operations: Facilities, Lines, Assets, Telemetry, OT Devices.
Energy: Overview, Tariffs, Market/Signals.
Intelligence: Forecasting, Risk, Constraints, Optimization, Dispatch.
Value: Verification, Savings, Arbitrage.
Knowledge: AI Copilot, Documents.
Platform: Sync, Jobs, Integrations, System Health, Simulator.
Governance: Users/Roles, Audit/Security, Settings.

## Command Center

Current load, headroom/threshold, 30m forecast, peak risk, alerts, proposals, estimated/verified savings,
telemetry health, edge/cloud state. Main chart overlays actual, forecast, threshold, tariff bands and event markers.
Pipeline strip: Telemetry -> Forecast -> Risk -> Optimize -> Dispatch -> Verify. Synthetic values show SIMULATED.

## Page patterns

List: filter/saved views/sort/virtualized table/details drawer. Detail: identity/status header + tabs + activity/audit.
All pages implement loading, empty, first-run, offline, stale, degraded, denied, error, retrying, success,
simulated, maintenance and disconnected states.

## Detailed operational screens

Asset: overview/live/historical/constraints/maintenance/optimization/dispatch/alerts/docs/audit.
Telemetry: live stream, explorer, quality, ingestion stats, compare/overlay/export.
OT: registry, connection, mappings/tags, commands, diagnostics, security.
Forecast: actual vs forecast, horizon, model/version, quality/error.
Risk: evidence, probability/severity, expected window, lifecycle.
Optimization: input snapshot, candidate matrix, constraint results, proposal/explanation.
Dispatch: queue, command detail, approval, transition timeline, adapter response, verification.
Finance: baseline vs actual, tariff/method, formula breakdown, estimate vs verified.
AI: chat + evidence; authorized query inspector.
Desktop extras: tray, optional start-on-login, native notifications, shortcuts, diagnostics export, updater state.
