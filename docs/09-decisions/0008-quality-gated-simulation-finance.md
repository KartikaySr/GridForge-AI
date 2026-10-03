# ADR 0008 — Quality-gated simulation finance

Status: accepted for Phase 7. Date: 2026-09-29.

The local finance module follows a completed Phase 6 simulator command. It cannot dispatch or
authorize machines. A versioned, user-entered simulation tariff is immutable and includes an
explicit currency, UTC applicability, nonoverlapping time-priced energy bands and a billing
period with optional demand rate. No real tariff or savings is inferred from defaults.

The baseline is the linked forecast's first projected facility kW value, produced before
dispatch by the declared rolling-mean method. This flat baseline is a transparent synthetic
counterfactual, not proof of causation. Execution and equal-length rebound windows use whole UTC
seconds. The comparison requires one timely, GOOD, unflagged SIMULATOR point per baseline asset
per second, with the prediction's exact mapping revision. There is no interpolation or silently
imputed data. A missing, duplicate, bad, late or uncovered slot makes the case INCOMPLETE, with
no verified ledger entry. The five-second delay allows on-time arrivals before final evaluation.

An ESTIMATED ledger entry prices commanded reduction during execution when the tariff covers
that window. A VERIFIED ledger entry, created only after complete execution and rebound, prices
baseline minus actual energy during execution and subtracts positive rebound consumption under
the appropriate band in each interval. Negative net values are recorded as losses. Decimal is
used for rates and arithmetic, and currency is rounded only for ledger amounts. The verification
retains prediction, proposal, command and tariff IDs, UTC windows, row bounds and input digests.
All case, ledger and outbox mutations commit atomically in SQLite and replay by request UUID.

Demand-charge savings remain INCOMPLETE even when a rate is entered. A short dispatch reduction
cannot establish change in an entire billing-period peak; interval averaging, ratchets and
utility rules may alter value. This decision follows [US DOE demand-charge guidance](https://www.energy.gov/sites/prod/files/2013/11/f4/standby_rates.pdf)
and [NREL demand-charge analysis](https://www.nrel.gov/docs/fy17osti/69016.pdf). Full
billing-period demand evidence and tariff-specific rules are required before this component can
be calculated. No performance fee, utility settlement, finalization or real-world verified
savings is implemented.

SQLite v6 adds tariff, verification, ledger and outbox tables; PostgreSQL central truth and
edge/cloud sync remain future phases. The native bridge exposes only fixed finance operations,
and the backend checks the provisioned local session's facility scope/capability/expiry. This
session is a simulation capability, not production human identity or separation of duties.
