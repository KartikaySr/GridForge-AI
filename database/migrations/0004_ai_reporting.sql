-- Administrator migration. The runtime AI role receives no base-table access.
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='gridforge_ai_reader') THEN
  CREATE ROLE gridforge_ai_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
 END IF;
END $$;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA IF NOT EXISTS ai_reporting;
REVOKE ALL ON SCHEMA ai_reporting FROM PUBLIC;
GRANT USAGE ON SCHEMA ai_reporting TO gridforge_ai_reader;
CREATE OR REPLACE VIEW ai_reporting.ai_telemetry WITH (security_barrier=true) AS
 SELECT org_id::text, facility_id::text, sequence AS row_id,
 body->'payload'->>'asset_id' AS asset_id,
 body->'payload'->>'event_time' AS observed_at,
 (body->'payload'->>'value')::numeric AS value_kw,
 body->'payload'->>'quality' AS quality,
 (body->'payload'->'flags')::text AS flags
 FROM public.sync_events
 WHERE stream='telemetry'
 AND org_id=NULLIF(current_setting('gridforge.org_id',true),'')::uuid
 AND facility_id=NULLIF(current_setting('gridforge.facility_id',true),'')::uuid;
GRANT SELECT ON ai_reporting.ai_telemetry TO gridforge_ai_reader;
REVOKE ALL ON public.sync_events, public.sync_edges, public.sync_stream_cursors,
 public.sync_conflict_audit FROM gridforge_ai_reader;
