# API & Event Contract Blueprint

Base `/api/v1`; FastAPI OpenAPI becomes executable source for generated clients.
Groups: auth, organizations, facilities, lines, assets, devices, signal-mappings, telemetry, energy, tariffs, models,
forecasts, risks, optimization, dispatch, verification, financials, alerts, ai, knowledge, reports, integrations,
sync, audit, system.

Conventions: structured errors(code,message,details,request_id); cursor pagination for large streams; ISO timestamps;
idempotency keys for replayable mutations; optimistic version for mutable config; freshness/source on operational state.
Examples: POST /telemetry/batches; GET /facilities/{id}/state; GET /telemetry; POST /optimization/runs;
POST /dispatch/{id}/approve; POST /dispatch/{id}/cancel; GET /dispatch/{id}/timeline; POST /sync/batches;
POST /ai/diagnose; GET /system/health.

Event envelope and catalog are defined in DOMAIN_AND_EVENTS. Event schemas eventually live under
`packages/events/schemas/` and are contract-tested across Python/TypeScript. Do not hand-maintain incompatible
client interfaces after OpenAPI generation exists.

## Phase 0 scaffold delta

No new routes or events. GET /health adds mode=SIMULATION and check=liveness; this is not readiness.
Dashboard metrics add mode=SIMULATION and source=simulation-scaffold. The current proposal adds
mode=SIMULATION and source=static-fixture. Existing fields remain illustrative and are not the
future financial/forecast contracts. TS/Python telemetry drift remains documented Phase 2 debt.

## Phase 1 local runtime contracts

The independent edge.runtime application exposes authenticated GET /api/v1/system/health and
GET /api/v1/system/diagnostics. Python Pydantic models are the executable source. Exported
OpenAPI and generated TS types live in packages/api-client. Both schema and generation drift
are checked. Requests require the native-owned bearer session and reject browser Origin.
No other Phase 0 routes are mounted. Runtime health declares shell-only readiness and
operational_ready=false, plus explicit unimplemented/unconfigured components.

Native runtime_status/runtime_restart/runtime_stop/runtime_diagnostics are desktop-local IPC
commands, not shared domain events. No operational events were added in Phase 1. Domain event
schema versioning and outbox work remain deferred. Diagnostics are ephemeral, not audit history.

## Phase 2 executable telemetry contracts

All native runtime routes require the private bearer session and reject browser Origin.
OpenAPI and generated TypeScript remain executable sources in packages/api-client.

- POST /api/v1/telemetry/batches: 1–100 scoped simulation points; commit acknowledgment with
  accepted/duplicates. Whole-batch scope/replay conflicts reject with 409; size 413; validation
  422; queue/store/worker unavailable 429. Structured errors never echo malformed input.
- GET /api/v1/telemetry/state: versioned simulation snapshot, latest five asset states, quality,
  recent 100 points, durable counts, queue and storage capacity, pending outbox, seed/tick.
- GET /api/v1/telemetry: descending row cursor `before`, optional synthetic `asset`, limit 1–100.
- GET /api/v1/telemetry/events: ascending `after` row cursor, at most 100 durable envelopes.
- GET /api/v1/telemetry/stream: SSE `event: snapshot`, ID=durable row cursor, data is
  TelemetrySnapshot. Full snapshot on connect/reconnect; repeated cursor during stale/disconnected
  periods is valid. Last-Event-ID is not replay semantics; use event history for lossless replay.
- POST /api/v1/simulator/scenario: normal/spike/bad/stale/disconnected, session-local simulation.

TelemetryPoint includes version, org/facility/line/asset/device/signal, metric, finite value,
unit, source quality, event time, sequence and UUID idempotency key. StoredPoint adds canonical
kW, received time, flags and row_id. TelemetryReceived schema version 1 wraps each committed
point with scope, event ID, correlation/causation and idempotency IDs. State/outbox commit together.
No other domain events are claimed implemented yet; quality changes are exposed in snapshot
state and point flags. Sync uploading/acknowledgement is deferred.

Native-only additions: simulator_scenario and telemetry_history. Runtime status includes the
latest SSE telemetry snapshot and receipt time. Runtime health now identifies telemetry
readiness, persistent synthetic facility scope and storage/worker components while retaining
operational_ready=false. Generated TS types supersede legacy scaffold types for this path.

## Phase 3 registry contracts

- GET /api/v1/registry returns scoped versioned records, connector diagnostics, metadata-only
  flexibility eligibility and configuration outbox count.
- POST /api/v1/registry accepts RegistryWrite(entity, expected_revision, request_id). Discriminated
  entity kinds: organization, facility, line, asset, device, metric, mapping. Revision 0 creates;
  exact current revision updates. Same request ID/content replays safely. 409 indicates scope,
  revision, replay, reference, disable-order, duplicate mapping or capacity conflict; malformed
  models and unsupported protocols/writable fields return structured 422. Authentication and body
  limits apply before domain processing.
- GET /api/v1/registry/events?after=N returns up to 100 ConfigurationChanged v1 envelopes in
  durable sequence order. Use the last envelope's sequence as the next cursor. Events and edits
  commit atomically; cloud acknowledgment is deferred.

RegistryRecord contains revision and typed entity. Scope is fixed to the runtime's persisted
organization/facility. Asset constraints are metadata, never authorization. Devices and mappings
require writable=false and protocol=SIMULATOR. Only active_power/kW is commissioned.
Telemetry IDs now accept registered identifiers rather than SIM-1..5 alone. New StoredPoint
mapping_id/mapping_revision are nullable for historical Phase 2 compatibility. Normalization
uses registered unit/scale/offset. Facility name/timezone and asset labels are registry-derived.
The original fixture generator is retained for legacy tests; runtime uses the registry adapter.

Native additions: registry_read and registry_save, limited to these fixed backend routes.
No generic URL, credential, database, protocol command or physical write capability is exposed.
Generated OpenAPI/TypeScript includes all registry models and structured errors.

## Phase 4 forecasting and risk contracts

- GET /api/v1/intelligence: scoped IntelligenceSnapshot with current quality/expiry assessment,
  latest immutable Prediction, model versions, scalar evaluation summary, latest 20 risks (open
  first), optional simulation threshold, worker failure and capacity/outbox counts.
- GET /api/v1/forecasts?before=N: up to 20 predictions, newest sequence first. Pass the last
  sequence as the next exclusive cursor. Historical READY status describes issuance; use the
  intelligence snapshot for current readiness.
- GET /api/v1/intelligence/events?after=N: up to 20 envelopes, ascending durable sequence.
  Pass the last sequence for the next cursor. No cloud ACK endpoint exists yet.
- Facility adds nullable simulation_demand_threshold_kw through the existing versioned registry
  write. Missing threshold means risk UNKNOWN; no operational safety limit is implied.

IntelligenceEvent v1 carries ForecastGenerated, ForecastFailed, ForecastEvaluated, RiskDetected,
RiskUpdated, RiskResolved and RiskSuperseded. Each includes scope, actor, UTC time, durable sequence,
event/idempotency IDs, prediction correlation/causation ID, and typed prediction/evaluation/risk
payload. State and event writes are transactional. Model/feature versions and input provenance
are explicit; null confidence/probability means uncalibrated. API authentication, Origin rejection,
structured errors and server-owned scope continue to apply.

Native intelligence_read reads only the fixed snapshot endpoint. Model inference, threshold
comparison, persistence and lifecycle logic live outside React. Health adds forecast-risk worker
status but operational_ready remains false. See ADR 0005 for target, quality and evaluation semantics.

## Phase 5 optimization contracts

- GET /api/v1/optimization: OptimizationSnapshot, up to 100 immutable policy versions, latest
  full run, currentness, facility timezone, capacity and pending outbox counts.
- POST /api/v1/optimization/policies: PolicyWrite(request_id, policy); saves a new immutable
  OptimizationPolicy. Policy carries effective UTC window, duration/total bounds, relative
  asset penalties and optional synthetic energy rate/currency. Scope is server-owned.
- POST /api/v1/optimization/runs: RunRequest(request_id, policy_id, duration_seconds); returns
  OptimizationRun with status PROPOSED, INFEASIBLE or NO_ACTION. No override/command fields.
- GET /api/v1/optimization/runs?before=N: newest-first exclusive sequence cursor, one full run
  per page to bound large evidence/candidate responses.
- GET /api/v1/optimization/events?after=N: ascending exclusive sequence cursor, at most 100.

Policies and runs replay by request UUID; conflicting payloads return 409. Unknown policy or
penalty asset returns 409, invalid inputs 422, full capacity 429, oversized request 413.
Native optimization_request exposes only fixed read/policy/run/history operations. It never
accepts arbitrary paths, tokens, database queries or adapter commands. Contracts are generated.

OptimizationPolicyCreated, OptimizationStarted, ProposalCreated, OptimizationInfeasible and
OptimizationNoAction v1 carry standard scoped envelopes with resource ID and request correlation.
Run and lifecycle events commit atomically. Every run embeds full policy/configuration/current
telemetry evidence and links immutable prediction/risk IDs. Proposal has NOT_AUTHORIZED and an
explicit evidence expiry. EconomicEstimate distinguishes ESTIMATED from INCOMPLETE and stores
Decimal strings, formula and exclusions. Neither status denotes verified savings.

## Phase 6 human approval and simulated dispatch

- GET `/api/v1/dispatch`: scoped DispatchSnapshot with fixed local session actor/capabilities,
  expiry, latest 20 durable commands, pending outbox count and worker status.
- POST `/api/v1/dispatch/requests`: ApprovalRequest(request_id, run_id, behavior) creates one
  PENDING_APPROVAL command for a feasible Phase 5 run after current hard-constraint validation.
  Behavior is `normal`, `delayed_ack`, `missing_ack` or `failed_command`, visibly simulation only.
- POST `/api/v1/dispatch/decisions`: DecisionRequest(request_id, command_id,
  expected_revision, action, reason) records explicit approve/reject/cancel. Approval queues
  only after another current validation; version mismatch is 409. Timeout rejects approval.
- GET `/api/v1/dispatch/{command_id}` returns command and its durable timeline.
- GET `/api/v1/dispatch/events?after=N` returns up to 100 ascending envelopes. Native dispatch
  detail exposes a command's timeline without a generic event query.

The API checks server-owned `dispatch.*` capability, local org/facility scope and session
expiry, returning 403 for denial. Native `dispatch_request` accepts only read/detail/request/
decision; it validates detail UUIDs and cannot pass an arbitrary path or identity. External
scope, role, authorization and command fields fail strict validation. All mutating requests have
UUID idempotency receipts; same request/body returns its original response, conflicting replay
returns 409. The body limit remains 64 KiB.

Phase 6 event names are ApprovalRequested, ApprovalGranted, ApprovalRejected,
DispatchQueued, DispatchSent, DispatchRetried, DispatchAcknowledged, DispatchExecuting,
DispatchCompleted, DispatchFailed, DispatchCancelled, DispatchRejected. Envelopes have
schema_version 1, org/facility, command correlation, causation/request ID, actor, UTC time,
revision, previous/next states and reason. All transitions and events commit atomically.
COMPLETED remains a simulated state, not a savings or verification state.

## Phase 7 simulation finance

- GET `/api/v1/finance`: scoped FinanceSnapshot with immutable tariff versions, latest 20
  verification cases, latest 100 ledger entries, pending outbox count and worker status.
- POST `/api/v1/finance/tariffs`: TariffWrite(request_id, tariff) stores an immutable user-entered
  simulation version with UTC effective/billing windows, ISO currency, nonoverlapping energy
  bands, and optional demand rate. There is no built-in utility tariff.
- POST `/api/v1/finance/verifications`: VerificationRequest(request_id, command_id, tariff_id)
  accepts only a COMPLETED simulated command and a versioned tariff. One verification case per
  command. Its pre-dispatch forecast ID, proposal, command and tariff are bound immutably.
- GET `/api/v1/finance/events?after=N`: up to 100 ascending finance outbox envelopes.

Native `finance_request` accepts only read/tariff/verify. Requests are bound to server-owned
facility scope, session expiry and `finance.read`, `tariff.update` or `finance.verify` capability.
Strict bodies reject client role/scope fields; request UUID replay is idempotent and conflicting
replay returns 409. Version-1 events are TariffVersionCreated, VerificationStarted,
SavingsEstimated, SavingsVerified, VerificationCompleted and VerificationIncomplete. Ledger and
events commit with their case under one SQLite transaction. The ledger has distinct ESTIMATED
and VERIFIED entries; demand-charge assessment is explicitly INCOMPLETE with no amount.

Verification uses the prediction's flat rolling-mean baseline for each whole UTC second in
execution and an equal-length rebound interval. Every baseline asset needs exactly one GOOD,
unflagged, matching-mapping SIMULATOR observation received within five seconds. Incomplete
coverage or tariff gaps produce no verified entry. A complete case records measured reduction,
baseline/actual energy, positive rebound energy, band-priced gross/rebound/net value, row ranges
and source digests. All amounts are Decimal currency values labeled SIMULATION.

## Phase 8 edge/cloud synchronization

The native local API adds authenticated GET `/api/v1/sync` with the persistent edge UUID,
facility scope, `NOT_CONFIGURED`/`OFFLINE`/`SYNCING`/`SYNCHRONIZED`/`CONFLICT` state, six
per-stream local and acknowledged cursors, pending counts, oldest pending UTC time/age, last
success and bounded conflict audit. Native `sync_read` is read-only and fixed-route.

The separate cloud receiver exposes authenticated GET `/api/v1/sync/state` and POST
`/api/v1/sync/batches`. Both require a provisioned 256-bit bearer token and `X-Edge-ID`; no
browser Origin is accepted. A batch has schema version 1, edge UUID, one stream and 1–20 entries
with contiguous local sequence, event UUID, canonical SHA-256 digest and versioned event body.
The receiver derives org/facility scope from its enrollment table and validates top-level and
nested scope and SIMULATION mode. It stores immutable JSONB events and a per-edge/per-stream
cursor in one PostgreSQL transaction, then returns the committed acknowledgement. Matched
replays are harmless; changed digest/event ID, gaps or scope mismatch return 409. The edge
persists an acknowledgement only after checking the response and matching its own contiguous
batch. A lost response causes replay, never a cloud-initiated dispatch or finance mutation.

There are six independent streams: telemetry, registry, intelligence, optimization, dispatch
and finance. Reconnect fetches cloud cursors and checks local divergence before upload.
Conflicted streams are quarantined with audit history; unaffected streams continue. Phase 8
has no downlink for configuration or commands, no remote OT control, and no blind finance
overwrite. Future Web/Mobile clients consume central visibility contracts, not native IPC.

## Phase 9 AI/RAG

Executable models live in `services/ai/contracts.py`; generated runtime OpenAPI/TypeScript
contracts are shared across clients. Native `ai_request` accepts only read/document/ask/query/
feedback operations with a 64 KiB bound; query IDs must be UUIDs. No arbitrary route is exposed.

- GET `/api/v1/ai`: scoped metadata, own recent answers, availability, selected backends and
  permission flags. No credentials. `ai.use` required.
- POST `/api/v1/ai/documents`: idempotent immutable plain-text revision ingestion, `ai.ingest`.
- POST `/api/v1/ai/ask`: idempotent conversation turn, KNOWLEDGE or ANALYTICS. SQL override requires
  `ai.inspect`; analytics also requires its domain read permission. Returns cited evidence or
  explicit NO_EVIDENCE/REJECTED/UNAVAILABLE. Advisory-only and SIMULATION are contract literals.
- GET `/api/v1/ai/queries/{uuid}`: own query inspector, `ai.inspect` plus domain read permission.
- POST `/api/v1/ai/feedback`: idempotent own-answer feedback and audit, `ai.use`.

Server identity supplies scope; bodies cannot supply org/facility/actor/permissions. Conversation
IDs and query IDs cannot cross actor or facility boundaries. Revision/key conflicts and request-ID
payload conflicts return 409. Permission failures return 403. AI service errors are isolated.

Version-1 `edge.ai` events add a seventh durable sync stream. Events contain actor, scope,
correlation/causation/idempotency IDs, resource ID and outcome. Document bodies, SQL, question
text and answer content remain local unless knowledge is explicitly published. SQLite v8 and
central sync migration 0003 preserve prior cursors and add the AI cursor. Upgrade central receivers
before v8 edges; older receivers cannot acknowledge the new stream contract.

## Phase 10 local security contracts

The native transport credential remains mandatory on all runtime routes. Human sign-in is additionally required for domain routes. `/api/v1/identity` reports setup/session status; POST `identity/bootstrap` creates the first ORG_ADMIN; POST `identity/login` and `identity/logout` change the local session. GET/POST `identity/users` and POST `identity/users/change` require `user.manage`; changes use `expected_revision` and revoke prior sessions. Role/scope in arbitrary request bodies cannot grant authority.

GET `security/audit?after=N` returns at most 100 audit rows, integrity status and head; GET `system/metrics` returns bounded-label request aggregates; GET `system/bundle` returns an explicitly redacted JSON bundle; GET `system/authorize` gates native lifecycle actions. Health/basic diagnostics and identity bootstrap/login/status remain transport-only for startup recovery. Responses expose request and correlation trace IDs. DTOs are generated from runtime OpenAPI; schema 9 adds local identity, audit, metrics and migration provenance without changing the seven domain synchronization streams.

## Phase 11 demonstration contracts

GET `/api/v1/demo` returns the isolated accelerated DemoSnapshot. POST `/api/v1/demo` accepts a DemoStep containing a request UUID and ordered action. Both require `system.configure` in the host facility; approval additionally requires `dispatch.approve`. Responses explicitly label SIMULATION, ACCELERATED_ISOLATED and ephemeral scope, preserving separate demo IDs. Successful UUID retries return the original result; conflicting or out-of-order actions reject. The domain chain, event versions and seven sync streams are reused unchanged. No migration or cloud command API is introduced.

## Phase 12A production reporting

GET `/api/v1/reports` and POST `/api/v1/reports/history` return descending pages of 20 immutable local reports. History accepts an optional positive exclusive `before` sequence. POST `/api/v1/reports/production` takes a request UUID, product, closed whole-second UTC interval, selected assets, Decimal good/rejected tonnes and context. Requires `report.create`; read/history/compare require `report.read`. Scope and actor are server-owned. POST `/api/v1/reports/compare` takes baseline/comparison UUIDs and returns explicit comparability reasons with a nullable SEC percentage change.

Native `security_request` allowlists reports, report-history, report-create and report-compare to fixed routes. Request replay is idempotent; changed payload reuse rejects. Reports use schema version 1, SIMULATION and LOCAL_ONLY literals. SQLite schema 10 adds immutable report storage; no central migration or sync-stream change. ProductionWrite input/output schemas differ because Decimal inputs accept JSON strings/numbers while outputs preserve decimal strings. See [reporting workflow and limitations](../06-engineering/PRODUCTION_REPORTING.md).

## Phase 12B demand-risk incidents

GET `/api/v1/incidents` and POST `/api/v1/incidents/history` (optional positive `before` cursor) return pages of 20 scoped incidents with processing cursor, backlog and worker error. POST `/api/v1/incidents/actions` requires UUID request/incident IDs, expected revision, acknowledge/resolve action and nonblank note. Read requires `alert.read`; mutation requires `alert.manage`. The API derives tenant/facility and actor from the authenticated session. `resolve` administratively closes a reviewed incident; it cannot resolve an active source risk. SUPERSEDED remains a distinct source state even after incident closure.

Incident schema version 1 includes scope, source risk/prediction IDs and SIMULATION/LOCAL_ONLY literals. Native security bridge allowlists incidents, incident-history and incident-action. SQLite schema 11 retains immutable workflow history and an atomic intelligence-source cursor. No cloud migration, remote dispatch or additional sync stream. See [incident workflow](../06-engineering/INCIDENT_WORKFLOW.md).
