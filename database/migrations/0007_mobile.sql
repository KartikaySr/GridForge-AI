ALTER TABLE portal_sessions ADD COLUMN IF NOT EXISTS client text NOT NULL DEFAULT 'web'
 CHECK(client IN ('web','mobile'));
CREATE TABLE IF NOT EXISTS mobile_reports (
 user_id uuid NOT NULL REFERENCES portal_users(id), request_id uuid NOT NULL,
 edge_id uuid NOT NULL REFERENCES sync_edges(edge_id),
 text text NOT NULL CHECK(length(text) BETWEEN 1 AND 2000),
 received_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(user_id,request_id)
);
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='gridforge_mobile_writer') THEN
  CREATE ROLE gridforge_mobile_writer NOLOGIN;
 END IF;
END $$;
GRANT gridforge_portal_reader TO gridforge_mobile_writer;
GRANT SELECT,INSERT ON mobile_reports TO gridforge_mobile_writer;
ALTER TABLE mobile_reports ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS mobile_report_read ON mobile_reports;
CREATE POLICY mobile_report_read ON mobile_reports FOR SELECT TO gridforge_mobile_writer
 USING(user_id=NULLIF(current_setting('gridforge.portal_user',true),'')::uuid);
DROP POLICY IF EXISTS mobile_report_write ON mobile_reports;
CREATE POLICY mobile_report_write ON mobile_reports FOR INSERT TO gridforge_mobile_writer
 WITH CHECK(user_id=NULLIF(current_setting('gridforge.portal_user',true),'')::uuid
 AND EXISTS(SELECT 1 FROM sync_edges e WHERE e.edge_id=mobile_reports.edge_id AND e.enabled));
