CREATE TABLE model_versions (version TEXT PRIMARY KEY, body TEXT NOT NULL CHECK(json_valid(body)));
CREATE TABLE predictions (sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE, run_key TEXT NOT NULL UNIQUE, org_id TEXT NOT NULL, facility_id TEXT NOT NULL, as_of TEXT NOT NULL, body TEXT NOT NULL CHECK(json_valid(body)));
CREATE INDEX predictions_scope_time ON predictions(org_id,facility_id,as_of);
CREATE TABLE forecast_evaluations (prediction_id TEXT PRIMARY KEY REFERENCES predictions(id), body TEXT NOT NULL CHECK(json_valid(body)));
CREATE TABLE risks (id TEXT PRIMARY KEY, org_id TEXT NOT NULL, facility_id TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('OPEN','RESOLVED','SUPERSEDED')), body TEXT NOT NULL CHECK(json_valid(body)));
CREATE UNIQUE INDEX risk_one_open ON risks(org_id,facility_id) WHERE state='OPEN';
CREATE TABLE intelligence_outbox (sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, body TEXT NOT NULL CHECK(json_valid(body)), acknowledged INTEGER NOT NULL DEFAULT 0 CHECK(acknowledged IN (0,1)));
CREATE INDEX telemetry_time ON telemetry(event_time);
