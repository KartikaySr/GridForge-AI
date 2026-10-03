CREATE TABLE optimization_policies (
 id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
 fingerprint TEXT NOT NULL, body TEXT NOT NULL CHECK(json_valid(body))
);
CREATE TABLE optimization_runs (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
 request_id TEXT NOT NULL UNIQUE, fingerprint TEXT NOT NULL,
 policy_id TEXT NOT NULL REFERENCES optimization_policies(id),
 body TEXT NOT NULL CHECK(json_valid(body))
);
CREATE TABLE optimization_outbox (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
 body TEXT NOT NULL CHECK(json_valid(body)), acknowledged INTEGER NOT NULL DEFAULT 0 CHECK(acknowledged IN (0,1))
);
