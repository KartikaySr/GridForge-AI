# GridForge AI — Master Codex Engineering Directive
Read `docs/00-master/CONTEXT_INDEX.md` before coding.

## Product
GridForge AI is an industrial energy-intelligence, flexibility, optimization and Industrial VPP platform.
Desktop/Edge is the operational control plane; future Web is enterprise visibility; future Mobile is field
input/alerts/approved actions. They are three clients of one platform and MUST share domain/API/event contracts.

## Non-negotiable chain
TELEMETRY -> VALIDATION -> STATE -> FORECAST -> RISK -> CONSTRAINTS -> OPTIMIZATION -> PROPOSAL ->
AUTHORIZATION -> DISPATCH -> ACKNOWLEDGEMENT -> VERIFICATION -> SAVINGS -> AUDIT.
Never implement ML/LLM -> MACHINE. Models advise/predict. Hard constraints and authorization remain authoritative.

## Prototype boundary
Default is SIMULATION. Real OT write capability is out of scope until separately commissioned with site-specific
safety engineering, interlocks, allowlisted points, command bounds, authorization, failsafe and validation.
Never present simulated control or synthetic savings as real.

## Architecture rules
- Modular monolith first; split services only for demonstrated need.
- Domain logic never lives only in React/routes.
- UI never talks directly to OT protocols or databases.
- Version API/events/models/policies/tariffs.
- PostgreSQL is central durable truth; edge has explicit local continuity + sync semantics.
- Cross-boundary events are versioned and idempotent; durable sync uses an outbox.
- Tenant/facility scope is server-enforced; RLS is defense in depth.
- AI Text-to-SQL uses a separate SELECT-only role and allowlisted views.
- Currency uses Decimal/NUMERIC; UTC at rest; facility timezone for presentation.
- Every prediction, proposal, approval, dispatch, verification and savings result is traceable.
- Estimated savings and verified savings are different states.
- Never hardcode secrets, tenant IDs, safety limits or real tariff claims.

## Delivery protocol
Before coding: identify phase, acceptance criteria, files/contracts/migrations affected, safety/security impact.
After coding: run format/lint/typecheck/tests, report results, list mocks/TODOs, update docs/contracts.
No phase is complete merely because it renders.
