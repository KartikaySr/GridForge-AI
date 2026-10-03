-- Optional central knowledge store; requires pgvector, never needed for local continuity.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS ai_knowledge;
REVOKE ALL ON SCHEMA ai_knowledge FROM PUBLIC;
CREATE TABLE IF NOT EXISTS ai_knowledge.documents (
 id uuid PRIMARY KEY, org_id uuid NOT NULL, facility_id uuid NOT NULL,
 document_key text NOT NULL, revision integer NOT NULL, digest text NOT NULL,
 metadata jsonb NOT NULL, active boolean NOT NULL,
 UNIQUE(org_id,facility_id,document_key,revision)
);
CREATE TABLE IF NOT EXISTS ai_knowledge.chunks (
 id uuid PRIMARY KEY, document_id uuid NOT NULL REFERENCES ai_knowledge.documents(id),
 org_id uuid NOT NULL, facility_id uuid NOT NULL,
 embedding_model text NOT NULL CHECK(embedding_model='token-hash-256-v1'),
 embedding vector(256) NOT NULL, evidence jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS ai_chunks_scope ON ai_knowledge.chunks(org_id,facility_id);
ALTER TABLE ai_knowledge.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_knowledge.documents FORCE ROW LEVEL SECURITY;
ALTER TABLE ai_knowledge.chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_knowledge.chunks FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS documents_scope ON ai_knowledge.documents;
CREATE POLICY documents_scope ON ai_knowledge.documents USING (
 org_id=NULLIF(current_setting('gridforge.org_id',true),'')::uuid AND
 facility_id=NULLIF(current_setting('gridforge.facility_id',true),'')::uuid
) WITH CHECK (
 org_id=NULLIF(current_setting('gridforge.org_id',true),'')::uuid AND
 facility_id=NULLIF(current_setting('gridforge.facility_id',true),'')::uuid
);
DROP POLICY IF EXISTS chunks_scope ON ai_knowledge.chunks;
CREATE POLICY chunks_scope ON ai_knowledge.chunks USING (
 org_id=NULLIF(current_setting('gridforge.org_id',true),'')::uuid AND
 facility_id=NULLIF(current_setting('gridforge.facility_id',true),'')::uuid
) WITH CHECK (
 org_id=NULLIF(current_setting('gridforge.org_id',true),'')::uuid AND
 facility_id=NULLIF(current_setting('gridforge.facility_id',true),'')::uuid
);
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='gridforge_knowledge_writer') THEN
  CREATE ROLE gridforge_knowledge_writer NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
 END IF;
END $$;
GRANT USAGE ON SCHEMA ai_knowledge TO gridforge_ai_reader, gridforge_knowledge_writer;
GRANT SELECT ON ai_knowledge.documents, ai_knowledge.chunks TO gridforge_ai_reader;
GRANT SELECT,INSERT,UPDATE ON ai_knowledge.documents TO gridforge_knowledge_writer;
GRANT SELECT,INSERT ON ai_knowledge.chunks TO gridforge_knowledge_writer;
