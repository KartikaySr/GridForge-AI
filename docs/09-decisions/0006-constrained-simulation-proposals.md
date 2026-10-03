# ADR 0006 — Constrained simulation proposals

Status: accepted for Phase 5. Date: 2026-09-28.

The optimizer creates advisory proposals only. It has no dependency on a dispatch adapter,
no physical-write route, and no approval shortcut. Existing native bearer authentication,
Origin rejection and server-owned local organization/facility scope apply.

## Supported optimization problem

`bounded-curtailment-v1` covers the current forecast peak above the configured simulation
threshold with continuous, constant asset reductions for a requested 60–1800 second window.
It minimizes separable relative per-kW penalties with deterministic asset-ID tie breaking.
The sorted greedy allocation is appropriate for this restricted linear problem; it is not a
mixed-integer production scheduler, load-shifting planner, or production economic optimum.
No candidate actions are accepted from the client. All assets, including rejected assets,
appear in the persisted candidate matrix. Failed global gates yield no selections.

Hard gates check current forecast/telemetry, organization/facility/line/asset availability,
noncritical and explicitly flexible simulated capability, enabled device/mapping and exact
mapping revision, fresh good unflagged telemetry, min/max loads, maximum reduction, overlapping
maintenance, policy window/duration/total bounds and forecast horizon. Nonzero minimum runtime
or downtime requirements fail closed because trustworthy operating-state history does not yet
exist. Only curtailment is supported: shifting/restart/max-shift actions cannot be requested.
Soft penalties never turn a rejected asset into eligible capacity. Insufficient flexibility
is INFEASIBLE; no excess with good inputs is NO_ACTION.

## Policies and provenance

Every policy save creates a new immutable UUID version (schema version 1), with an explicit
UTC effective/allowed window and user-supplied bounds. Existing versions remain selectable and
authoritative for historical replay. A run stores its full policy, registry snapshot/digest,
current normalized telemetry, prediction/risk IDs, every constraint result, selected reductions,
algorithm version and optional proposal. Forecast evidence remains available through the
immutable prediction. Policy and run request UUIDs enforce replay with payload-conflict rejection.
No client can supply scope, bypass flags, selected actions or authorization.

SQLite migration 4 adds policies, runs and an outbox. Evidence evaluation, run and event writes
share the ingestion/configuration lock and commit together. One local repository owns one
organization/facility; central Postgres execution and RLS remain later integration work.
Policies cap at 100 and runs at 500, rejecting additional writes rather than deleting audit
history. History returns one full run per cursor page; event pages return up to 100 envelopes.
Maximum outbox growth is 1100 events at those capacities. Sync ACK is Phase 8.
Native GET responses retain the 256 KiB bound except optimization's bounded full snapshots,
which allow 2 MiB. Policy/run request bodies retain the 64 KiB limit.

## Money and freshness

A missing simulation rate yields INCOMPLETE with null money. An explicit user-entered rate
produces an ESTIMATED, SIMULATED gross avoided-energy value using Decimal: reduction kW ×
seconds / 3600 × rate, rounded half-up to 0.01 simulation currency units. This is not a real
versioned utility tariff, net savings, demand-charge value, load-shifting arbitrage or verified
finance. Rebound, production cost and other exclusions are stored with the estimate. The
immutable policy ID versions this synthetic rate assumption; real tariff models are Phase 7.

Proposal evidence expires within five seconds (or sooner with forecast/policy expiry). The
snapshot also invalidates currentness after registry changes, bad/stale/disconnected telemetry
or a backwards clock. UI receipt freshness and expiry guard display independently. Historical
PROPOSED records remain immutable; replay does not issue a fresh proposal or extend expiry.
All proposals state NOT_AUTHORIZED. Phase 6 must independently revalidate current constraints
and authorization before any simulated dispatch; a historical proposal is never permission.
