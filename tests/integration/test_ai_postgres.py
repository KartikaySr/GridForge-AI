"""AI SQL permissions and pgvector scope against a real temporary PostgreSQL instance."""

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from cloud.repository import CloudRepository
from edge.storage.repository import Repository
from scripts.publish_knowledge import publish
from services.ai.contracts import AskRequest
from services.ai.postgres import PgVectorKnowledge, execute_postgres
from services.ai.service import AIService
from services.sync.service import SyncService
from simulator.factory import factory_batch
from tests.integration.test_sync_postgres import DirectTransport, enroll
from tests.integration.test_sync_postgres import postgres as postgres
from tests.unit.test_ai import document, principal
from tests.unit.test_forecasting import ORIGIN

ROOT = Path(__file__).parents[2]


def reporting(dsn: str) -> None:
    CloudRepository(dsn).migrate()
    with psycopg.connect(dsn) as conn:
        conn.execute((ROOT / "database/migrations/0004_ai_reporting.sql").read_text())


def test_postgres_scoped_analytics_and_database_role(postgres: str) -> None:
    reporting(postgres)
    repo = Repository(None)
    cloud = CloudRepository(postgres)
    token = enroll(cloud, repo)
    repo.ingest(
        factory_batch(repo.org_id, repo.facility_id, repo.seed, 1, ORIGIN, "normal"), ORIGIN
    )
    service = AIService(repo)
    service.ask(AskRequest(request_id=uuid4(), question="hello"), principal(repo))
    SyncService(repo, token=token, transport=DirectTransport(cloud)).tick(ORIGIN)
    result = execute_postgres(
        postgres, "SELECT asset_id,value_kw FROM ai_telemetry", repo.org_id, repo.facility_id
    )
    assert result.status == "SUCCEEDED" and len(result.rows) == 5
    assert (
        execute_postgres(
            postgres,
            "SELECT asset_id FROM ai_telemetry WHERE 1=1 OR quality='GOOD'",
            uuid4(),
            repo.facility_id,
        ).rows
        == []
    )
    assert (
        execute_postgres(
            postgres, "SELECT token_sha256 FROM sync_edges", repo.org_id, repo.facility_id
        ).status
        == "REJECTED"
    )
    for sql in [
        "SELECT * FROM public.sync_edges",
        "DELETE FROM public.sync_events",
        "CREATE TABLE public.ai_escape(id int)",
    ]:
        with psycopg.connect(postgres) as conn:
            conn.execute("SET ROLE gridforge_ai_reader")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql)
            conn.rollback()
    with psycopg.connect(postgres) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM sync_events WHERE edge_id=%s AND stream='ai'", (repo.edge_id,)
        ).fetchone() == (1,)
    repo.close()


def test_pgvector_ingestion_retrieval_rls_and_revision(postgres: str, tmp_path: Path) -> None:
    reporting(postgres)
    migration = (ROOT / "database/migrations/0005_ai_vectors.sql").read_text()
    with psycopg.connect(postgres) as conn:
        available = conn.execute(
            "SELECT 1 FROM pg_available_extensions WHERE name='vector'"
        ).fetchone()
        if not available:
            # Local test-only library loading avoids installing into the user's PostgreSQL.
            directory = os.environ.get("GRIDFORGE_TEST_PGVECTOR_DIR")
            if not directory:
                pytest.skip(
                    "pgvector absent; set GRIDFORGE_TEST_PGVECTOR_DIR to a compiled checkout"
                )
            base = Path(directory)
            library = base / "vector.so"
            sql = (base / "sql/vector--0.8.0.sql").read_text()
            sql = "\n".join(line for line in sql.splitlines() if not line.startswith("\\"))
            sql = sql.replace("MODULE_PATHNAME", str(library))
            conn.execute(sql)
            migration = migration.replace("CREATE EXTENSION IF NOT EXISTS vector;", "")
        conn.execute(migration)
    path = tmp_path / "knowledge.db"
    repo = Repository(path)
    ai, user = AIService(repo), principal(repo)
    write = document()
    metadata = ai.ingest(write, user)
    evidence = ai.retrieve("compressor maintenance approval", user)
    central = PgVectorKnowledge(postgres)
    central.store(metadata, evidence)
    central.store(metadata, evidence)
    result = central.retrieve("compressor maintenance approval", repo.org_id, repo.facility_id)
    assert result and result[0].digest == evidence[0].digest
    assert central.retrieve("compressor maintenance approval", uuid4(), repo.facility_id) == []
    with psycopg.connect(postgres) as conn:
        conn.execute("SET ROLE gridforge_ai_reader")
        assert conn.execute("SELECT COUNT(*) FROM ai_knowledge.chunks").fetchone() == (0,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM ai_knowledge.chunks")
        conn.rollback()
    newer = ai.ingest(
        write.model_copy(
            update={
                "request_id": uuid4(),
                "revision": 2,
                "text": "Compressor maintenance requires a signed permit.",
            }
        ),
        user,
    )
    central.store(newer, ai.retrieve("compressor maintenance", user))
    assert (
        central.retrieve("compressor maintenance", repo.org_id, repo.facility_id)[0].revision == 2
    )
    third = ai.ingest(
        write.model_copy(
            update={
                "request_id": uuid4(),
                "revision": 3,
                "text": "Compressor maintenance permit checklist. " * 150,
            }
        ),
        user,
    )
    assert third.chunk_count > 4
    assert publish(path, postgres) == 3
    with psycopg.connect(postgres) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM ai_knowledge.chunks WHERE document_id=%s", (third.id,)
        ).fetchone() == (third.chunk_count,)
    assert (
        central.retrieve("compressor maintenance", repo.org_id, repo.facility_id)[0].revision == 3
    )
    repo.close()
