# GridForge Desktop-First Architecture

## Current slice

Phase 1: Tauri/React shell -> allowlisted native IPC -> Rust process supervisor -> authenticated
loopback FastAPI edge runtime -> bounded health/diagnostics. No operational state is implemented.

Phase 0 reference: simulator -> separate legacy FastAPI -> in-memory prototype state. The old
dashboard component is retained but unmounted; its unauthenticated API is not used by the desktop.

## Production evolution

OT/Simulator -> Edge ingestion -> SQLite local state/outbox -> feature pipeline -> forecasting -> risk -> constraints -> optimization -> approval -> simulated dispatch -> acknowledgement -> verification -> financial attribution -> audit.

Edge outbox -> idempotent cloud synchronization -> central FastAPI/domain runtime -> PostgreSQL/pgvector.
The edge store is purpose-built for local continuity; it is not a full clone of the central database.

## Shared platform

`packages/contracts` is intentionally independent from Desktop so Web and Mobile can consume the same domain vocabulary.

## Desktop modules

Command Center, Facilities, Assets, Telemetry, Energy, Forecasting, Optimization, Dispatch, Arbitrage, Alerts, AI Copilot, Integrations, Audit, Settings.

## Safety boundary

The starter exposes no physical-machine actuation. Optimization is advisory/simulated.
