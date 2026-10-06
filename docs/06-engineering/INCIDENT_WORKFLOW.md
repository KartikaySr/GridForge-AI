# Prototype demand-risk incident workflow

The alert worker consumes the durable intelligence outbox in ascending batches of at most 100. Risk events create or update one incident per risk ID. The projection and cursor commit together: a crash or failed transaction does not skip source events. On restart the worker resumes at the stored cursor. Source risk history remains authoritative; incidents never change predictions, authorization, commands or savings.

Open **Alerts & Incidents** after signing in. Refresh retrieves the newest 20 records with UTC observation time, source-processing backlog and worker failure state. Older pages use an exclusive cursor; refresh returns to the latest page. This is an explicit-refresh history screen, not a push-notification service.

All authenticated roles can read. Operators, energy/facility managers and administrators can investigate. Enter a nonblank note and acknowledge an OPEN incident. An ACKNOWLEDGED incident can be closed only after its source risk is RESOLVED or SUPERSEDED, checked against both the projection and authoritative risk record. SUPERSEDED means evidence/configuration invalidated the old risk; closure does not mean demand is safe. Current risk stays visible separately in Forecasting & Risk.

Each action requires an expected revision and request UUID. Identical retries return the original result; conflicting payloads reject. Refresh after a revision conflict, review changed evidence and submit a new action. API permissions, scope and session expiry are enforced independently of button visibility. Changes append immutable incident history with actor/note. Source events retain the prediction/risk evidence; runtime POST audit records the human action and correlation ID.

SQLite migration 11 adds incidents, immutable history, action replay records and a durable source cursor. History capacity is 20,000 entries; exhaustion stops processing visibly without advancing the cursor. Snapshot includes pending events and a sanitized worker error. Shutdown waits for any in-flight projection transaction before closing the repository.

All incident workflow records are LOCAL_ONLY; no new central sync stream, SMS, email, OS notification, configurable alert rule or remote action is introduced. JSON report export belongs to Production & Reports; incident timeline export is a later extension. Back up the database before upgrading; schema-11 databases must not be opened by older runtimes.
