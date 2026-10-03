CREATE TABLE IF NOT EXISTS ai_documents (
 id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, fingerprint TEXT NOT NULL,
 org_id TEXT NOT NULL, facility_id TEXT NOT NULL, document_key TEXT NOT NULL,
 revision INTEGER NOT NULL, active INTEGER NOT NULL, body TEXT NOT NULL CHECK(json_valid(body)),
 UNIQUE(org_id,facility_id,document_key,revision)
);
CREATE TABLE IF NOT EXISTS ai_chunks (
 id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES ai_documents(id),
 ordinal INTEGER NOT NULL, start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL,
 text TEXT NOT NULL, digest TEXT NOT NULL, embedding TEXT NOT NULL CHECK(json_valid(embedding)),
 UNIQUE(document_id,ordinal)
);
CREATE TABLE IF NOT EXISTS ai_conversations (
 id TEXT PRIMARY KEY, org_id TEXT NOT NULL, facility_id TEXT NOT NULL, actor TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_answers (
 id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, fingerprint TEXT NOT NULL,
 conversation_id TEXT NOT NULL REFERENCES ai_conversations(id),
 body TEXT NOT NULL CHECK(json_valid(body))
);
CREATE TABLE IF NOT EXISTS ai_queries (
 id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES ai_conversations(id),
 body TEXT NOT NULL CHECK(json_valid(body))
);
CREATE TABLE IF NOT EXISTS ai_feedback (
 id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, fingerprint TEXT NOT NULL,
 answer_id TEXT NOT NULL REFERENCES ai_answers(id), body TEXT NOT NULL CHECK(json_valid(body)),
 note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_outbox (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
 body TEXT NOT NULL CHECK(json_valid(body)), acknowledged INTEGER NOT NULL DEFAULT 0
);
-- Rebuild the stream constraint to admit AI audit references without changing old cursors.
CREATE TEMP TABLE sync_conflicts_backup AS SELECT * FROM sync_conflicts;
DROP TABLE sync_conflicts;
CREATE TABLE IF NOT EXISTS sync_streams_v8 (
 stream TEXT PRIMARY KEY CHECK(stream IN ('telemetry','registry','intelligence','optimization','dispatch','finance','ai')),
 acknowledged_sequence INTEGER NOT NULL DEFAULT 0 CHECK(acknowledged_sequence>=0),
 last_success_at TEXT, last_error TEXT, conflict_code TEXT
);
INSERT OR IGNORE INTO sync_streams_v8 SELECT * FROM sync_streams;
INSERT OR IGNORE INTO sync_streams_v8(stream) VALUES ('ai');
DROP TABLE sync_streams;
ALTER TABLE sync_streams_v8 RENAME TO sync_streams;
CREATE TABLE sync_conflicts (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 stream TEXT NOT NULL REFERENCES sync_streams(stream),
 sequence INTEGER NOT NULL, code TEXT NOT NULL, detected_at TEXT NOT NULL,
 detail TEXT NOT NULL, resolved INTEGER NOT NULL DEFAULT 0 CHECK(resolved IN (0,1))
);
INSERT INTO sync_conflicts SELECT * FROM sync_conflicts_backup;
DROP TABLE sync_conflicts_backup;
CREATE VIEW IF NOT EXISTS ai_telemetry AS
 SELECT json_extract(payload,'$.org_id') AS org_id,
 json_extract(payload,'$.facility_id') AS facility_id,
 id AS row_id, asset_id, event_time AS observed_at,
 json_extract(payload,'$.value') AS value_kw,
 json_extract(payload,'$.quality') AS quality,
 json_extract(payload,'$.flags') AS flags FROM telemetry;
CREATE VIEW IF NOT EXISTS ai_dispatch AS
 SELECT json_extract(body,'$.org_id') AS org_id,
 json_extract(body,'$.facility_id') AS facility_id,
 id AS command_id, json_extract(body,'$.state') AS state,
 json_extract(body,'$.updated_at') AS observed_at FROM dispatch_commands;
CREATE VIEW IF NOT EXISTS ai_savings AS
 SELECT json_extract(body,'$.org_id') AS org_id,
 json_extract(body,'$.facility_id') AS facility_id,
 id AS entry_id, status, json_extract(body,'$.currency') AS currency,
 json_extract(body,'$.amount') AS amount,
 json_extract(body,'$.occurred_at') AS observed_at FROM finance_ledger;
