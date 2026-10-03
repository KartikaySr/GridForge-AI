# ADR 0005 — Measurable baseline forecasting and advisory risk

Status: Phase 4 simulation prototype. No optimization or actuation authority.

## Decision and model contract

The local modular monolith owns a forecasting service and a separate pure risk lifecycle.
Model `facility-demand-baseline`, immutable version `rolling-mean-v1`, uses feature version
`minute-coverage-v1`. Model metadata is durably registered and compared on startup; conflicting
definitions under an existing version fail closed. This baseline has no fitted parameters.
XGBoost/LightGBM are deferred until representative data and measured improvement justify them.
No additional dependencies or central PostgreSQL changes are required.

Forecast target: each minute's mean facility active power over the 30 minutes following the UTC
minute origin. Five past minute bins supply a rolling mean held flat across the horizon. This is
a deliberately simple measurable baseline, not a calibrated probability model, billing demand
calculation, or accurate industrial predictor. Confidence and risk probability are explicitly null.

## Features and quality

The pipeline uses normalized persisted kW from all enabled assets with telemetry capability.
An asset without a mapping cannot disappear from the expected asset set. Each minute needs at
least 48 distinct good event-time seconds per asset, consistent with the 1 Hz prototype source.
Repeated samples within a second cannot inflate coverage. A bad/flagged/mismatched-mapping sample
invalidates its second. Remaining good samples are averaged per asset and summed across assets.
There is no zero fill, forward fill, synthetic history or interpolation of missing asset demand.

Only event times inside the feature window and receipts available at the prediction origin may
enter features. Future events and later backfills cannot leak into an earlier forecast. Current
quality/freshness is separately required; stale, bad, disconnected, missing and mapping-changed
states suppress inference. Historical Phase 2 rows lacking mapping provenance are not assumed
compatible. A configuration change invalidates the current snapshot until recomputation.

Prediction evidence includes five input bins, minimum asset coverage, asset membership, mapping
versions, registry SHA-256, source-row SHA-256, row bounds/count and UTC input window. The digest
hashes ordered immutable source records; it is provenance, not a cryptographic audit signature.
Prediction records include scoped identity, model version, target, units, horizon, optional
simulation threshold and facility revision. Insufficient input persists a DEGRADED result with
an empty value list and a reason. Current results expire after 65 seconds from the minute origin.

## Runtime and durability

Migration 0003 adds model_versions, predictions, forecast_evaluations, risks and a separate
intelligence_outbox, plus time/scope indexes. Existing identity/configuration/telemetry is retained.
Inference runs in a joined background thread every five seconds, independent of UI navigation.
It persists once per minute/configuration/live-quality state, using a deterministic scoped UUID
and unique run key. Replays across restarts return the stored result without duplicate events.

Predictions and risk changes commit with their events in one SQLite transaction. Evaluation
commits with its own event. Telemetry continues if inference fails. Health exposes the failure;
snapshot numbers are not represented as current after worker failure or expiry. Cancellation
joins the inference DB user before runtime storage closes.

The prototype retains up to 1,440 prediction attempts and 10,000 intelligence events. Capacity
rejects new writes, preserves evidence and reports failure. Due evaluation is still attempted
when new predictions have reached capacity. No silent pruning or cloud ACK is implemented.
The previous telemetry capacity also applies. A single scoped facility owns this edge store.

## Evaluation

Prospective rolling-origin validation uses immutable predictions issued before their future
actuals. At least 30 minutes plus a five-second receipt allowance must elapse before scoring.
All 30 future bins must pass the same coverage/mapping rules. Missing/corrupt actuals produce
UNKNOWN evaluation, not zero error. A changed mapping does not silently validate an older model
input regime. One chronological pending origin is evaluated per five-second worker cycle.

Metrics: MAE and RMSE in kW; MAPE excludes zero actuals and is null if no nonzero actuals exist;
peak precision/recall compare the maximum predicted/actual minute mean with the threshold stored
on that prediction. Undefined denominators return null. Aggregate MAPE weights valid samples;
MAE/RMSE combine complete 30-bin windows. Overlapping horizons are correlated, not independent
validation trials. Tests prove known errors on held-out future windows and leakage exclusion;
these fixture results are not an industrial accuracy claim. No training accuracy is displayed.

## Risk lifecycle and configuration

Facility configuration gains optional simulation_demand_threshold_kw, positive finite kW.
There is no default threshold: missing configuration means UNKNOWN risk. Registry revision,
idempotency, scope checks and ConfigurationChanged audit apply to threshold edits.

A valid prediction reaching the configured threshold opens one HIGH advisory risk per facility.
Later breaches update it. A fresh complete forecast below the same threshold resolves it.
Missing/bad input never resolves an open risk. Facility revision changes supersede existing
risks and allow assessment under the new revision, including name/timezone edits; this conservative
behavior is explicit. No operator acknowledgement, approval, dispatch or safety-limit change is
implied. Risk records retain first/latest prediction IDs, threshold/revision, expected window,
predicted peak and transition reason. Every transition has an immutable event snapshot.

## API, native and UI

Authenticated fixed endpoints expose intelligence snapshots, descending prediction history and
ascending intelligence events. Shared Pydantic/OpenAPI/TypeScript contracts serve future clients.
Tauri adds only intelligence_read against the fixed snapshot route; no arbitrary URL or DB access.
The native transport retains its 256 KiB response ceiling. A snapshot contains one prediction,
model definitions, scalar evaluation metrics and the latest 20 risks with open risks first.

Forecasting & Risk shows the baseline curve against historical input means, optional threshold,
model/evidence, quality, risk lifecycle and evaluation. Timestamps use the facility timezone.
Disconnected/expired/degraded states hide the current curve and mark current risk UNKNOWN while
retaining historical provenance. Browser preview cannot manufacture predictions. Full histories
are API-accessible; the UI focuses on current intelligence and the latest 20 risks.

## Deferred qualification

Central model governance, alternate metrics/cadences, trained models, calibrated intervals,
site accuracy objectives, drift monitoring, user RBAC, signed packaging, durable store ownership,
industrial-scale throughput and retention/ACK policies require later work. Domain services do
not call an optimizer, dispatch adapter or physical machine.
