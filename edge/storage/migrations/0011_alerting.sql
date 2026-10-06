CREATE TABLE incidents (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT,
 id TEXT NOT NULL UNIQUE,
 risk_id TEXT NOT NULL UNIQUE,
 body TEXT NOT NULL CHECK(json_valid(body))
);
CREATE TABLE incident_requests (
 request_id TEXT PRIMARY KEY,
 fingerprint TEXT NOT NULL,
 body TEXT NOT NULL CHECK(json_valid(body))
);
CREATE TABLE incident_history (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT,
 incident_id TEXT NOT NULL,
 event_type TEXT NOT NULL,
 body TEXT NOT NULL CHECK(json_valid(body))
);
CREATE TRIGGER incident_history_no_update BEFORE UPDATE ON incident_history
 BEGIN SELECT RAISE(ABORT,'INCIDENT_HISTORY_IMMUTABLE'); END;
CREATE TRIGGER incident_history_no_delete BEFORE DELETE ON incident_history
 BEGIN SELECT RAISE(ABORT,'INCIDENT_HISTORY_IMMUTABLE'); END;
CREATE TABLE incident_cursor (singleton INTEGER PRIMARY KEY CHECK(singleton=1), sequence INTEGER NOT NULL);
INSERT INTO incident_cursor VALUES (1,0);
