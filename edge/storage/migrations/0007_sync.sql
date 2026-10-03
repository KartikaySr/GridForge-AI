CREATE TABLE edge_identity (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 edge_id TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL
);
CREATE TABLE sync_streams (
 stream TEXT PRIMARY KEY CHECK(stream IN ('telemetry','registry','intelligence','optimization','dispatch','finance')),
 acknowledged_sequence INTEGER NOT NULL DEFAULT 0 CHECK(acknowledged_sequence>=0),
 last_success_at TEXT,
 last_error TEXT,
 conflict_code TEXT
);
INSERT INTO sync_streams(stream) VALUES
 ('telemetry'),('registry'),('intelligence'),('optimization'),('dispatch'),('finance');
CREATE TABLE sync_conflicts (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 stream TEXT NOT NULL REFERENCES sync_streams(stream),
 sequence INTEGER NOT NULL,
 code TEXT NOT NULL,
 detected_at TEXT NOT NULL,
 detail TEXT NOT NULL,
 resolved INTEGER NOT NULL DEFAULT 0 CHECK(resolved IN (0,1))
);
