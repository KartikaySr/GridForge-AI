ALTER TABLE sync_stream_cursors DROP CONSTRAINT IF EXISTS sync_stream_cursors_stream_check;
ALTER TABLE sync_stream_cursors ADD CONSTRAINT sync_stream_cursors_stream_check
 CHECK(stream IN ('telemetry','registry','intelligence','optimization','dispatch','finance','ai'));
INSERT INTO sync_stream_cursors(edge_id,stream)
 SELECT edge_id,'ai' FROM sync_edges ON CONFLICT DO NOTHING;
