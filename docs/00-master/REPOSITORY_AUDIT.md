# Repository audit and Phase 0 boundary

The initial folder contained 56 files and no .git metadata. Every existing source and
specification file was inspected before modification. The initial Python and JSON syntax
checks passed; there were no installed workspace dependencies or automated tests.

## Initial implementation

Browser React/Vite command center; five FastAPI endpoints; process-local latest telemetry;
five static assets; random Python telemetry producer; eight disconnected PostgreSQL table
definitions; shared TS scaffold interfaces; CSS tokens; placeholder domain/edge/test folders.
No native desktop, auth, edge DB, outbox, dispatch, verification or AI execution existed.

## Gaps and phase ownership

| Area                   | Existing limitation                                         | Phase |
| ---------------------- | ----------------------------------------------------------- | ----- |
| Engineering            | No locks, CI, quality gates or tests                        | 0     |
| Desktop/runtime        | Browser and manually started API only                       | 1     |
| Telemetry              | Non-deterministic, ephemeral, no freshness/quality pipeline | 2     |
| Facility/assets/OT     | Static records, incomplete ownership                        | 3     |
| Forecast/risk          | Arithmetic fixtures with no evaluation or provenance        | 4     |
| Optimization           | Fixed proposal; no hard/soft constraint evaluation          | 5     |
| Authorization/dispatch | No execution or state machine                               | 6     |
| Finance                | Fixed amounts without verification/tariffs                  | 7     |
| Sync                   | No outbox/cursors/reconciliation                            | 8     |
| AI                     | Placeholder directory                                       | 9     |
| Enterprise             | No full RBAC, recovery, packaging or performance checks     | 10    |
| Demonstration          | No integrated decision chain                                | 11    |

## Conflicts and resolutions

- The old summary diagram omitted SQLite edge continuity. Detailed architecture controls:
  SQLite edge store plus central PostgreSQL. The summary is aligned in Phase 0.
- services/ does not imply microservices. ADR 0001 records logical module ownership.
- The UI described fabricated savings as verified. Phase 0 removes that claim and labels
  charts, forecasts, risk, assets, alerts, savings and proposals as illustrative.
- TS telemetry uses camelCase and quality; Python uses snake_case with no quality. This is
  recorded debt for Phase 2 executable contracts, not silently claimed as compatible.
- The supplied phase plan adds Phase 11 to the engineering document's original 0–10 list.

## Remaining security and architecture debt

Unauthenticated API; arbitrary asset IDs; unbounded process-local latest readings; no replay,
tenant/facility scope, durable audit or stale-data processing. Static assets do not follow live
load. Displayed asset-slot count is not throughput. The frontend polls and can partially refresh;
its connection badge does not establish freshness. Route-local calculations remain placeholders.
Money uses number/float-compatible response fields and INR-specific names until versioned
Decimal/string-money contracts replace them. SQL lacks RLS, migration tracking, complete
ownership, command history, policy/tariff versions and financial provenance.

The API's SIMULATION startup guard and loopback launch defaults are limited prototype safeguards,
not authentication or commissioning controls. No machine-write code exists. Production provider,
identity, tariff, settlement, signing and OT commissioning decisions remain open.
