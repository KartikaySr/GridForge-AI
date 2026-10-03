"""Explicit administrator export of local knowledge revisions into central pgvector."""

import os
import sqlite3
from argparse import ArgumentParser
from contextlib import closing
from pathlib import Path
from uuid import UUID

from services.ai.contracts import Evidence, KnowledgeDocument
from services.ai.postgres import PgVectorKnowledge


def publish(path: Path, dsn: str) -> int:
    central = PgVectorKnowledge(dsn)
    total = 0
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        for row in conn.execute("SELECT body FROM ai_documents ORDER BY document_key,revision"):
            document = KnowledgeDocument.model_validate_json(row["body"])
            chunks = [
                Evidence(
                    citation=f"D{chunk['ordinal'] + 1}",
                    document_id=document.id,
                    revision=document.revision,
                    title=document.title,
                    source=document.source,
                    chunk_id=UUID(chunk["id"]),
                    start=chunk["start_offset"],
                    end=chunk["end_offset"],
                    digest=chunk["digest"],
                    excerpt=chunk["text"],
                    score=0,
                )
                for chunk in conn.execute(
                    "SELECT * FROM ai_chunks WHERE document_id=? ORDER BY ordinal",
                    (str(document.id),),
                )
            ]
            central.store(document, chunks)
            total += 1
    return total


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--edge-db", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("GRIDFORGE_KNOWLEDGE_WRITER_DSN")
    if not dsn:
        parser.error("GRIDFORGE_KNOWLEDGE_WRITER_DSN must be configured")
    try:
        count = publish(args.edge_db, dsn)
    except Exception:
        raise SystemExit(
            "Knowledge publication failed; check revisions, scope and database permissions"
        ) from None
    print(f"Published or replayed {count} knowledge revisions")


if __name__ == "__main__":
    main()
