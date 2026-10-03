CREATE TABLE dispatch_commands (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE REFERENCES optimization_runs(id),
 state TEXT NOT NULL CHECK(state IN ('PENDING_APPROVAL','APPROVED','QUEUED','SENT','ACKNOWLEDGED','EXECUTING','COMPLETED','FAILED','CANCELLED','REJECTED')),
 body TEXT NOT NULL CHECK(json_valid(body))
);
-- One active facility-local command prevents overlapping or stacked reductions.
CREATE UNIQUE INDEX dispatch_one_active ON dispatch_commands((1))
 WHERE state NOT IN ('COMPLETED','FAILED','CANCELLED','REJECTED');
CREATE TABLE dispatch_requests (
 request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, response TEXT NOT NULL CHECK(json_valid(response))
);
CREATE TABLE dispatch_outbox (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
 command_id TEXT NOT NULL REFERENCES dispatch_commands(id),
 body TEXT NOT NULL CHECK(json_valid(body)), acknowledged INTEGER NOT NULL DEFAULT 0 CHECK(acknowledged IN (0,1))
);
CREATE INDEX dispatch_event_command ON dispatch_outbox(command_id,sequence);
CREATE TABLE simulator_commands (
 command_id TEXT PRIMARY KEY REFERENCES dispatch_commands(id),
 fingerprint TEXT NOT NULL, accepted_at TEXT NOT NULL,
 ack_at TEXT, started_at TEXT, ends_at TEXT,
 active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0,1))
);
