"""Optional central adapters. Trusted services supply scope; providers never supply DSNs."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from services.ai.contracts import Evidence, KnowledgeDocument, QueryRun
from services.ai.providers import EMBEDDING_MODEL, embed
from services.ai.sql import SQLRejected, compile_query


def scope(conn: psycopg.Connection, org_id: UUID, facility_id: UUID) -> None:
    conn.execute("SELECT set_config('gridforge.org_id',%s,true)", (str(org_id),))
    conn.execute("SELECT set_config('gridforge.facility_id',%s,true)", (str(facility_id),))


def execute_postgres(dsn: str, sql: str, org_id: UUID, facility_id: UUID) -> QueryRun:
    run = QueryRun(
        id=uuid4(),
        status="REJECTED",
        proposed_sql=sql,
        executed_sql=None,
        parameters=[],
        columns=[],
        rows=[],
        source_view=None,
        observed_at=datetime.now(UTC),
        error=None,
        result_digest=None,
    )
    try:
        compiled, view = compile_query(sql, "postgres")
        if view != "ai_telemetry":
            raise SQLRejected("CENTRAL_VIEW_NOT_AVAILABLE")
        run.executed_sql, run.source_view = compiled, view
        run.parameters = [str(org_id), str(facility_id)]
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET LOCAL ROLE gridforge_ai_reader")
            conn.execute("SET LOCAL statement_timeout='200ms'")
            conn.execute("SET LOCAL search_path=pg_catalog,ai_reporting")
            scope(conn, org_id, facility_id)
            cursor = conn.execute(compiled, run.parameters)
            run.columns = [column.name for column in cursor.description or []]
            run.rows = [
                [
                    value if value is None or isinstance(value, (str, int, float)) else str(value)
                    for value in row
                ]
                for row in cursor.fetchmany(100)
            ]
            run.status = "SUCCEEDED"
            run.result_digest = hashlib.sha256(
                json.dumps([run.columns, run.rows]).encode()
            ).hexdigest()
    except SQLRejected as exc:
        run.error = str(exc)
    except psycopg.Error:
        run.status, run.error = "UNAVAILABLE", "CENTRAL_QUERY_UNAVAILABLE"
    return run


class PgVectorKnowledge:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def store(self, document: KnowledgeDocument, evidence: list[Evidence]) -> None:
        with psycopg.connect(self.dsn, connect_timeout=2) as conn:
            conn.execute("SET LOCAL ROLE gridforge_knowledge_writer")
            scope(conn, document.org_id, document.facility_id)
            conn.execute("SET LOCAL statement_timeout='2s'")
            # Serialize revisions per logical document, and reject changed immutable content.
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (f"{document.org_id}:{document.facility_id}:{document.document_key}",),
            )
            old = conn.execute(
                "SELECT digest FROM ai_knowledge.documents WHERE id=%s", (document.id,)
            ).fetchone()
            if old:
                if old[0] != document.digest:
                    raise ValueError("DOCUMENT_REPLAY_CONFLICT")
                return
            revision = conn.execute(
                "SELECT COALESCE(MAX(revision),0) FROM ai_knowledge.documents "
                "WHERE document_key=%s",
                (document.document_key,),
            ).fetchone()
            if revision is None or document.revision != revision[0] + 1:
                raise ValueError("DOCUMENT_REVISION_CONFLICT")
            if len(evidence) != document.chunk_count or any(
                item.document_id != document.id
                or item.revision != document.revision
                or hashlib.sha256(item.excerpt.encode()).hexdigest() != item.digest
                for item in evidence
            ):
                raise ValueError("CHUNK_CONTRACT_INVALID")
            conn.execute(
                "UPDATE ai_knowledge.documents SET active=false WHERE document_key=%s",
                (document.document_key,),
            )
            conn.execute(
                "INSERT INTO ai_knowledge.documents VALUES (%s,%s,%s,%s,%s,%s,%s,true)",
                (
                    document.id,
                    document.org_id,
                    document.facility_id,
                    document.document_key,
                    document.revision,
                    document.digest,
                    Jsonb(document.model_dump(mode="json")),
                ),
            )
            for item in evidence:
                conn.execute(
                    "INSERT INTO ai_knowledge.chunks VALUES (%s,%s,%s,%s,%s,%s::vector,%s)",
                    (
                        item.chunk_id,
                        document.id,
                        document.org_id,
                        document.facility_id,
                        EMBEDDING_MODEL,
                        json.dumps(embed(item.excerpt)),
                        Jsonb(item.model_dump(mode="json")),
                    ),
                )

    def retrieve(self, question: str, org_id: UUID, facility_id: UUID) -> list[Evidence]:
        with psycopg.connect(self.dsn, connect_timeout=2) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET LOCAL ROLE gridforge_ai_reader")
            scope(conn, org_id, facility_id)
            conn.execute("SET LOCAL statement_timeout='200ms'")
            rows = conn.execute(
                "SELECT c.evidence,1-(c.embedding <=> %s::vector) AS score "
                "FROM ai_knowledge.chunks c JOIN ai_knowledge.documents d ON d.id=c.document_id "
                "WHERE c.org_id=%s AND c.facility_id=%s AND d.active "
                "AND c.embedding_model=%s ORDER BY c.embedding <=> %s::vector,c.id LIMIT 4",
                (
                    json.dumps(embed(question)),
                    org_id,
                    facility_id,
                    EMBEDDING_MODEL,
                    json.dumps(embed(question)),
                ),
            ).fetchall()
        return [
            Evidence.model_validate(row[0]).model_copy(
                update={"citation": f"D{index + 1}", "score": round(row[1], 6)}
            )
            for index, row in enumerate(rows)
            if row[1] >= 0.15
        ]
