CREATE TABLE production_reports (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT,
 id TEXT NOT NULL UNIQUE,
 request_id TEXT NOT NULL UNIQUE,
 fingerprint TEXT NOT NULL,
 payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE TRIGGER production_report_no_update BEFORE UPDATE ON production_reports
 BEGIN SELECT RAISE(ABORT,'REPORT_IMMUTABLE'); END;
CREATE TRIGGER production_report_no_delete BEFORE DELETE ON production_reports
 BEGIN SELECT RAISE(ABORT,'REPORT_IMMUTABLE'); END;
