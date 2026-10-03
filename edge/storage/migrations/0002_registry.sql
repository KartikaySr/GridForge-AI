CREATE TABLE registry (
    kind TEXT NOT NULL CHECK(kind IN ('organization','facility','line','asset','device','metric','mapping')),
    id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision>0),
    body TEXT NOT NULL CHECK(json_valid(body)),
    PRIMARY KEY(kind,id)
);
CREATE INDEX registry_scope ON registry(org_id,facility_id,kind);
CREATE TABLE configuration_outbox (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    request_id TEXT NOT NULL UNIQUE,
    fingerprint TEXT NOT NULL,
    body TEXT NOT NULL CHECK(json_valid(body)),
    acknowledged INTEGER NOT NULL DEFAULT 0 CHECK(acknowledged IN (0,1))
);
