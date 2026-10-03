CREATE TABLE identity (singleton INTEGER PRIMARY KEY CHECK(singleton=1), org_id TEXT NOT NULL, facility_id TEXT NOT NULL, seed INTEGER NOT NULL, tick INTEGER NOT NULL DEFAULT 0);
CREATE TABLE telemetry (id INTEGER PRIMARY KEY AUTOINCREMENT, idempotency_key TEXT NOT NULL UNIQUE, fingerprint TEXT NOT NULL, asset_id TEXT NOT NULL, event_time TEXT NOT NULL, sequence INTEGER NOT NULL, payload TEXT NOT NULL);
CREATE INDEX telemetry_asset_time ON telemetry(asset_id,event_time);
CREATE TABLE latest (asset_id TEXT PRIMARY KEY, telemetry_id INTEGER NOT NULL REFERENCES telemetry(id));
CREATE TABLE outbox (id INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, acknowledged INTEGER NOT NULL DEFAULT 0 CHECK(acknowledged IN (0,1)), FOREIGN KEY(id) REFERENCES telemetry(id));
CREATE TABLE counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL CHECK(value>=0));
INSERT INTO counters VALUES ('accepted',0),('duplicates',0),('rejected',0),('backpressure',0);
