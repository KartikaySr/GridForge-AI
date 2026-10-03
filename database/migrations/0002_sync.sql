-- Phase 8 cloud inbox. Apply to PostgreSQL independently of the illustrative 0001 domain schema.
CREATE TABLE IF NOT EXISTS sync_edges (
 edge_id uuid PRIMARY KEY,
 org_id uuid NOT NULL,
 facility_id uuid NOT NULL,
 token_sha256 text NOT NULL CHECK(length(token_sha256)=64),
 enabled boolean NOT NULL DEFAULT true,
 enrolled_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sync_stream_cursors (
 edge_id uuid NOT NULL REFERENCES sync_edges(edge_id),
 stream text NOT NULL CHECK(stream IN ('telemetry','registry','intelligence','optimization','dispatch','finance')),
 acknowledged_sequence bigint NOT NULL DEFAULT 0 CHECK(acknowledged_sequence>=0),
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(edge_id,stream)
);
CREATE TABLE IF NOT EXISTS sync_events (
 edge_id uuid NOT NULL REFERENCES sync_edges(edge_id),
 stream text NOT NULL,
 sequence bigint NOT NULL CHECK(sequence>0),
 event_id uuid NOT NULL,
 org_id uuid NOT NULL,
 facility_id uuid NOT NULL,
 event_type text NOT NULL,
 schema_version text NOT NULL,
 digest text NOT NULL CHECK(length(digest)=64),
 body jsonb NOT NULL,
 received_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(edge_id,stream,sequence),
 UNIQUE(edge_id,event_id),
 FOREIGN KEY(edge_id,stream) REFERENCES sync_stream_cursors(edge_id,stream)
);
CREATE INDEX IF NOT EXISTS sync_events_scope ON sync_events(org_id,facility_id,stream,sequence);
CREATE TABLE IF NOT EXISTS sync_conflict_audit (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 edge_id uuid NOT NULL REFERENCES sync_edges(edge_id),
 stream text NOT NULL,
 sequence bigint NOT NULL,
 code text NOT NULL,
 detected_at timestamptz NOT NULL DEFAULT now()
);
