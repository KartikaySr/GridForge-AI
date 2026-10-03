# Domain & Event Model

## Hierarchy

Organization -> Facility -> ProductionLine -> Asset -> Device/SignalMapping.
Facility carries timezone, utility/contract context, demand thresholds and policy. Asset carries rated load,
criticality, flexibility and constraints.

## Telemetry

TelemetryPoint: event_time, received_time, org/facility/asset/device, metric, value, unit, quality, source,
sequence/idempotency key. Aggregates are derived.

## Intelligence

ModelDefinition -> ModelVersion -> Prediction -> RiskEvent. Prediction records horizon, target, value,
interval/confidence when available, model version and input provenance.

## Optimization

OptimizationPolicy -> OptimizationRun -> CandidateEvaluation -> Proposal. Persist every candidate and every
hard/soft constraint result/rejection reason.

## Dispatch state

PROPOSED -> PENDING_APPROVAL -> APPROVED -> QUEUED -> SENT -> ACKNOWLEDGED -> EXECUTING ->
COMPLETED | FAILED | CANCELLED | REJECTED. Validate every transition and audit actor/time/reason.

## Verification/finance

Verification compares declared baseline with measured actual window. Savings records include method, inputs,
tariff version, units, provenance and status ESTIMATED/VERIFIED/FINALIZED.

## Event envelope

event_id, event_type, schema_version, occurred_at UTC, producer, org/facility, correlation_id, causation_id,
actor, idempotency_key, payload. Events report facts; commands request actions. Durable sync uses outbox.
Core events: TelemetryReceived/Rejected/QualityChanged, DeviceConnected/Disconnected, ForecastGenerated/Failed,
RiskDetected/Resolved, OptimizationStarted/ProposalCreated/Infeasible, ApprovalRequested/Granted/Rejected,
DispatchQueued/Sent/Acknowledged/Started/Completed/Failed, VerificationCompleted, SavingsEstimated/Verified,
AlertCreated/Acknowledged, SyncQueued/Succeeded/Conflict, ConfigurationChanged, SecurityEventRaised.
