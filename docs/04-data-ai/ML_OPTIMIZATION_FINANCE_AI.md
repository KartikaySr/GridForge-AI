# ML, Optimization, Finance & AI

## Forecasting

Quality gate -> resample/aggregate -> features -> inference -> prediction -> risk. Baseline model first, then
XGBoost/LightGBM. Features may include lag/rolling demand, gradient, hour/day, tariff, starts/utilization and
quality indicators; prevent future leakage. Evaluate time-based split with MAE/RMSE/MAPE where valid plus
peak-event precision/recall. Never claim near-perfect accuracy without evidence. Prediction stores model version
and input provenance; bad input yields degraded/unknown, not fabricated value.

## Optimization

Inputs: current state, forecast/risk, threshold, tariff, candidates, constraints, policy. Hard constraints include
commissioning/safety status, critical exclusions, min/max load, runtime/downtime, allowed windows, maintenance,
max shift, command bounds. Soft constraints include cost/production/wear/preference/fairness.
Persist every candidate result. Proposal stores selected actions, expected reduction, ESTIMATED savings, impact,
assumptions and versions. Infeasible means INFEASIBLE, never forced selection.

## Dispatch/verification

Authorization policy defines approvers. Simulation auto-approval only if explicitly configured and visibly simulated.
State machine is authoritative and idempotent. Verification compares expected vs measured reduction with quality.

## Finance

Separate opportunity, estimate, verified, finalized. Energy shifting compares baseline vs actual by tariff interval
and considers rebound where relevant. Demand-charge savings must use billing-period logic, not naive instantaneous
kW multiplication. Persist baseline method/version, actuals, tariff/version, formula inputs and currency. Performance
fee applies only to eligible verified savings.

## AI/RAG

Use cases: explanations, manuals/SOP retrieval, analytical questions. Document -> chunk -> metadata -> embedding ->
pgvector -> scoped retrieval. Text-to-SQL: resolve scope -> allowlisted semantic schema -> generate SELECT ->
parse/validate -> enforce row/time limits -> execute read-only -> synthesize with evidence -> audit.
Block DDL/DML/multiple statements/system catalogs/secret tables/scope escape in code/DB permissions, not prompt alone.
Provider abstraction; core platform works when AI is unavailable.
