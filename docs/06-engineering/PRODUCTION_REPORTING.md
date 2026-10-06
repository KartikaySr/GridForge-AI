# Production-normalized simulation reports

Phase 12A adds local reporting; it does not commission physical equipment, certify manufacturing quality or extend the savings ledger.

## Operator workflow

1. Start the desktop, sign in as an ORG_ADMIN, FACILITY_MANAGER or ENERGY_MANAGER, and collect simulator telemetry.
2. Open Production & Reports. Select a closed UTC interval, at whole-second boundaries, lasting 1–3,600 seconds. Allow five seconds after its end. Enter registered asset IDs, product/SKU, good and rejected tonnes, and operating context.
3. Create a simulation report. The server resolves asset mappings and scope; the caller cannot supply identity, permissions or calculated energy. All selected assets need exactly one valid normalized simulator power reading per second. Missing, duplicated, flagged, bad, late or mismatched-mapping data makes the report INCOMPLETE and withholds both energy and SEC.
4. Review immutable history and copy a JSON report. An unchanged retry after a connection failure reuses the request UUID. Conflicting reuse is rejected. Correct mistakes through a new declaration; old evidence remains.
5. Choose a baseline and later comparison. Their product, asset/mapping boundary and interval duration must match. Both need complete data and a positive baseline SEC. Decreased declared good-output rate or increased declared reject fraction prevents an improvement claim.

SEC = measured electricity / declared good tonnes. Percentage change = (comparison SEC / baseline SEC − 1) × 100; negative means lower SEC. The result describes two synthetic periods. It does not establish causality, preserved physical quality, whole-factory performance or utility settlement. Product identity alone does not normalize weather, utilization, material mix or operating conditions.

## Persistence and bounds

SQLite migration 0010 creates immutable production_reports with unique report and request identifiers. Maximum 10,000 reports; each query reads at most 100,000 telemetry rows. History uses descending exclusive sequence cursors with pages of 20. Reports retain the mapping revision, row range, source digest, actor, UTC time and declaration. Existing runtime middleware audits authenticated POST operations. Transport and human-session authorization both apply.

All reports explicitly state LOCAL_ONLY. They are covered by the SQLite backup/restore procedure but are not one of the seven synchronized event streams. No cloud visibility is implied. Source digests support traceability; they are not an external timestamp or tamper-proof attestation against a privileged database owner.

## Migration and recovery

Back up the stopped or live database through the documented SQLite backup helper before upgrading. Schema 10 is accepted by the updated recovery validator. Restoring an older backup creates a separate database; startup upgrades it in order. Do not open a schema-10 database with an older runtime. Preserve the old runtime and pre-upgrade backup for rollback; do not delete the reports table to simulate a downgrade.

## Verification

Tests cover complete and incomplete evidence, idempotency conflicts, persistence, immutability, comparisons, production regression, scope/role/expiry, API sign-in, cursor bounds and pagination. Screen tests check browser preview, read-only identities and request-ID preservation after uncertain failure. Native tests call report history through the fixed bridge. The frozen-runtime smoke checks reporting availability after sign-in.
