CREATE TABLE finance_tariffs (
 id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, fingerprint TEXT NOT NULL,
 body TEXT NOT NULL CHECK(json_valid(body))
);
CREATE TABLE finance_verifications (
 id TEXT PRIMARY KEY, command_id TEXT NOT NULL UNIQUE REFERENCES dispatch_commands(id),
 request_id TEXT NOT NULL UNIQUE, fingerprint TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('PENDING','VERIFIED','INCOMPLETE')),
 body TEXT NOT NULL CHECK(json_valid(body))
);
CREATE TABLE finance_ledger (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
 verification_id TEXT NOT NULL REFERENCES finance_verifications(id),
 status TEXT NOT NULL CHECK(status IN ('ESTIMATED','VERIFIED')),
 body TEXT NOT NULL CHECK(json_valid(body))
);
CREATE TABLE finance_outbox (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
 body TEXT NOT NULL CHECK(json_valid(body)), acknowledged INTEGER NOT NULL DEFAULT 0 CHECK(acknowledged IN (0,1))
);
