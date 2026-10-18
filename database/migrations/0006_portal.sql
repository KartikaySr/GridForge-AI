CREATE TABLE IF NOT EXISTS portal_users (
 id uuid PRIMARY KEY, username text UNIQUE NOT NULL, salt text NOT NULL,
 password_hash text NOT NULL, enabled boolean NOT NULL DEFAULT true
);
CREATE TABLE IF NOT EXISTS portal_memberships (
 user_id uuid REFERENCES portal_users(id), org_id uuid NOT NULL, facility_id uuid NOT NULL,
 PRIMARY KEY(user_id,org_id,facility_id)
);
CREATE TABLE IF NOT EXISTS portal_sessions (
 token_hash text PRIMARY KEY, user_id uuid REFERENCES portal_users(id), expires_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS portal_login_limit (
 singleton integer PRIMARY KEY CHECK(singleton=1), window_start timestamptz NOT NULL,
 attempts integer NOT NULL
);
INSERT INTO portal_login_limit VALUES(1,now(),0) ON CONFLICT DO NOTHING;
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='gridforge_portal_reader') THEN
  CREATE ROLE gridforge_portal_reader NOLOGIN;
 END IF;
END $$;
GRANT USAGE ON SCHEMA public TO gridforge_portal_reader;
GRANT SELECT ON sync_edges,sync_events,portal_memberships TO gridforge_portal_reader;
ALTER TABLE portal_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS portal_membership_read ON portal_memberships;
CREATE POLICY portal_membership_read ON portal_memberships FOR SELECT TO gridforge_portal_reader
 USING(user_id=NULLIF(current_setting('gridforge.portal_user',true),'')::uuid);
DROP POLICY IF EXISTS portal_edge_read ON sync_edges;
CREATE POLICY portal_edge_read ON sync_edges FOR SELECT TO gridforge_portal_reader USING(
 EXISTS(SELECT 1 FROM portal_memberships m WHERE m.org_id=sync_edges.org_id AND m.facility_id=sync_edges.facility_id)
);
DROP POLICY IF EXISTS portal_event_read ON sync_events;
CREATE POLICY portal_event_read ON sync_events FOR SELECT TO gridforge_portal_reader USING(
 EXISTS(SELECT 1 FROM portal_memberships m WHERE m.org_id=sync_events.org_id AND m.facility_id=sync_events.facility_id)
);
