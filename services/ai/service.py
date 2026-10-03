import hashlib
import json
import os
from datetime import UTC, datetime
from threading import Lock
from uuid import UUID, uuid4

from edge.storage.repository import Repository
from services.ai.contracts import (
    AskRequest,
    CopilotAnswer,
    CopilotSnapshot,
    DocumentWrite,
    Evidence,
    FeedbackReceipt,
    FeedbackWrite,
    KnowledgeDocument,
    QueryRun,
)
from services.ai.postgres import PgVectorKnowledge, execute_postgres
from services.ai.providers import (
    EMBEDDING_MODEL,
    AdvisoryProvider,
    LocalEvidenceProvider,
    UnavailableProvider,
    embed,
)
from services.ai.sql import VIEWS, SQLRejected, compile_query, execute_local
from services.dispatch.permissions import PermissionDenied, Principal
from services.sync.codec import digest


class AIRejected(ValueError):
    pass


VIEW_PERMISSIONS = {
    "ai_telemetry": "telemetry.read",
    "ai_dispatch": "dispatch.read",
    "ai_savings": "finance.read",
}


class AIService:
    def __init__(self, repo: Repository, provider: AdvisoryProvider | None = None) -> None:
        self.repo = repo
        self.provider = provider or (
            LocalEvidenceProvider()
            if os.environ.get("GRIDFORGE_AI_PROVIDER", "local") == "local"
            else UnavailableProvider()
        )
        self.busy = Lock()
        knowledge_dsn = os.environ.get("GRIDFORGE_AI_KNOWLEDGE_DSN")
        self.central_knowledge = PgVectorKnowledge(knowledge_dsn) if knowledge_dsn else None
        self.query_dsn = os.environ.get("GRIDFORGE_AI_QUERY_DSN")

    def require(self, principal: Principal, permission: str) -> None:
        principal.require(permission, self.repo.org_id, self.repo.facility_id, datetime.now(UTC))

    def audit(
        self, event_type: str, resource: UUID, principal: Principal, request_id: UUID
    ) -> None:
        # Same transaction as the domain write. No prompts, document bodies or SQL in sync events.
        event = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "schema_version": "1",
            "occurred_at": datetime.now(UTC).isoformat(),
            "producer": "edge.ai",
            "org_id": str(self.repo.org_id),
            "facility_id": str(self.repo.facility_id),
            "actor": principal.actor,
            "correlation_id": str(request_id),
            "causation_id": str(request_id),
            "idempotency_key": str(request_id),
            "resource_id": str(resource),
            "mode": "SIMULATION",
        }
        self.repo.db.execute(
            "INSERT INTO ai_outbox(event_id,body) VALUES (?,?)",
            (event["event_id"], json.dumps(event)),
        )

    def ingest(self, write: DocumentWrite, principal: Principal) -> KnowledgeDocument:
        self.require(principal, "ai.ingest")
        if not write.text.strip() or "\x00" in write.text:
            raise AIRejected("DOCUMENT_TEXT_REQUIRED")
        fingerprint = digest(write.model_dump(mode="json"))
        with self.repo.lock, self.repo.db:
            prior = self.repo.db.execute(
                "SELECT fingerprint,body FROM ai_documents WHERE request_id=?",
                (str(write.request_id),),
            ).fetchone()
            if prior:
                if prior[0] != fingerprint:
                    raise AIRejected("IDEMPOTENCY_CONFLICT")
                return KnowledgeDocument.model_validate_json(prior[1])
            count = self.repo.db.execute("SELECT COUNT(*) FROM ai_documents").fetchone()[0]
            if count >= 100:
                raise AIRejected("KNOWLEDGE_CAPACITY_REACHED")
            revision = self.repo.db.execute(
                "SELECT COALESCE(MAX(revision),0) FROM ai_documents "
                "WHERE org_id=? AND facility_id=? AND document_key=?",
                (str(self.repo.org_id), str(self.repo.facility_id), write.document_key),
            ).fetchone()[0]
            if write.revision != revision + 1:
                raise AIRejected("DOCUMENT_REVISION_CONFLICT")
            chunks = [
                (offset, write.text[offset : offset + 1000])
                for offset in range(0, len(write.text), 900)
            ]
            document = KnowledgeDocument(
                id=uuid4(),
                document_key=write.document_key,
                revision=write.revision,
                title=write.title,
                source=write.source,
                org_id=self.repo.org_id,
                facility_id=self.repo.facility_id,
                digest=hashlib.sha256(write.text.encode()).hexdigest(),
                created_at=datetime.now(UTC),
                chunk_count=len(chunks),
                embedding_model=EMBEDDING_MODEL,
                active=True,
            )
            self.repo.db.execute(
                "UPDATE ai_documents SET active=0 WHERE org_id=? AND facility_id=? "
                "AND document_key=?",
                (str(self.repo.org_id), str(self.repo.facility_id), write.document_key),
            )
            self.repo.db.execute(
                "INSERT INTO ai_documents VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    str(document.id),
                    str(write.request_id),
                    fingerprint,
                    str(self.repo.org_id),
                    str(self.repo.facility_id),
                    write.document_key,
                    write.revision,
                    1,
                    document.model_dump_json(),
                ),
            )
            for ordinal, (offset, text) in enumerate(chunks):
                self.repo.db.execute(
                    "INSERT INTO ai_chunks VALUES (?,?,?,?,?,?,?,?)",
                    (
                        str(uuid4()),
                        str(document.id),
                        ordinal,
                        offset,
                        offset + len(text),
                        text,
                        hashlib.sha256(text.encode()).hexdigest(),
                        json.dumps(embed(text)),
                    ),
                )
            self.audit("KnowledgeRevisionIngested", document.id, principal, write.request_id)
            return document

    def retrieve(self, question: str, principal: Principal) -> list[Evidence]:
        self.require(principal, "ai.use")
        if self.central_knowledge:
            return self.central_knowledge.retrieve(
                question, self.repo.org_id, self.repo.facility_id
            )
        vector = embed(question)
        with self.repo.lock:
            rows = self.repo.db.execute(
                "SELECT c.*,d.body FROM ai_chunks c JOIN ai_documents d ON d.id=c.document_id "
                "WHERE d.org_id=? AND d.facility_id=? AND d.active=1",
                (str(self.repo.org_id), str(self.repo.facility_id)),
            ).fetchall()
        ranked = []
        for row in rows:
            score = sum(a * b for a, b in zip(vector, json.loads(row["embedding"]), strict=True))
            if score >= 0.15:
                ranked.append((score, row))
        ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
        result = []
        for index, (score, row) in enumerate(ranked[:4]):
            metadata = KnowledgeDocument.model_validate_json(row["body"])
            result.append(
                Evidence(
                    citation=f"D{index + 1}",
                    document_id=metadata.id,
                    revision=metadata.revision,
                    title=metadata.title,
                    source=metadata.source,
                    chunk_id=UUID(row["id"]),
                    start=row["start_offset"],
                    end=row["end_offset"],
                    digest=row["digest"],
                    excerpt=row["text"],
                    score=round(score, 6),
                )
            )
        return result

    def owner(self, conversation_id: UUID, principal: Principal) -> None:
        row = self.repo.db.execute(
            "SELECT 1 FROM ai_conversations WHERE id=? AND org_id=? AND facility_id=? AND actor=?",
            (
                str(conversation_id),
                str(self.repo.org_id),
                str(self.repo.facility_id),
                principal.actor,
            ),
        ).fetchone()
        if not row:
            raise AIRejected("CONVERSATION_NOT_FOUND")

    def ask(self, write: AskRequest, principal: Principal) -> CopilotAnswer:
        self.require(principal, "ai.use")
        if write.sql is not None:
            self.require(principal, "ai.inspect")
        if not write.question.strip() or (write.sql is not None and write.intent != "ANALYTICS"):
            raise AIRejected("QUESTION_OR_INTENT_INVALID")
        if not self.busy.acquire(blocking=False):
            raise AIRejected("AI_BUSY_RETRY_SAME_REQUEST")
        try:
            return self._ask(write, principal)
        finally:
            self.busy.release()

    def _ask(self, write: AskRequest, principal: Principal) -> CopilotAnswer:
        fingerprint = digest(write.model_dump(mode="json"))
        with self.repo.lock:
            prior = self.repo.db.execute(
                "SELECT fingerprint,body FROM ai_answers WHERE request_id=?",
                (str(write.request_id),),
            ).fetchone()
            if prior:
                answer = CopilotAnswer.model_validate_json(prior[1])
                self.owner(answer.conversation_id, principal)
                if answer.query_id:
                    saved = self.repo.db.execute(
                        "SELECT body FROM ai_queries WHERE id=?", (str(answer.query_id),)
                    ).fetchone()
                    saved_query = QueryRun.model_validate_json(saved[0])
                    if saved_query.source_view:
                        self.require(principal, VIEW_PERMISSIONS[saved_query.source_view])
                if prior[0] != fingerprint:
                    raise AIRejected("IDEMPOTENCY_CONFLICT")
                return answer
            if self.repo.db.execute("SELECT COUNT(*) FROM ai_answers").fetchone()[0] >= 10000:
                raise AIRejected("AI_HISTORY_CAPACITY_REACHED")
            if write.conversation_id:
                self.owner(write.conversation_id, principal)
        answer = CopilotAnswer(
            id=uuid4(),
            request_id=write.request_id,
            conversation_id=write.conversation_id or uuid4(),
            question=write.question,
            answer="No matching evidence. Ingest a relevant document or use Analytics.",
            status="NO_EVIDENCE",
            provider=self.provider.name,
            created_at=datetime.now(UTC),
            evidence=[],
            query_id=None,
        )
        query: QueryRun | None = None
        try:
            if not self.provider.available:
                raise RuntimeError("Provider unavailable")
            if write.intent == "KNOWLEDGE":
                answer.evidence = self.retrieve(write.question, principal)
                if answer.evidence:
                    answer.answer = self.provider.answer(write.question, answer.evidence)[:6000]
                    answer.status = "ANSWERED"
            else:
                proposed = write.sql or self.provider.sql(write.question)
                if proposed:
                    try:
                        _, view = compile_query(proposed)
                        self.require(principal, VIEW_PERMISSIONS[view])
                    except SQLRejected:
                        pass  # Executor records the rejected query without running it.
                    query = (
                        execute_postgres(
                            self.query_dsn, proposed, self.repo.org_id, self.repo.facility_id
                        )
                        if self.query_dsn
                        else execute_local(
                            self.repo, proposed, self.repo.org_id, self.repo.facility_id
                        )
                    )
                    answer.query_id = query.id
                    if query.status == "SUCCEEDED":
                        answer.status = "ANSWERED"
                        answer.answer = (
                            f"[Q1] {len(query.rows)} row(s) from {query.source_view}; "
                            "at most the latest 1,000 scoped source rows were considered. "
                            "This is a bounded simulation snapshot, not a full-period report.\n"
                            + json.dumps(
                                {"columns": query.columns, "rows": query.rows}, ensure_ascii=False
                            )
                        )
                    else:
                        answer.status = query.status
                        answer.answer = f"Analytical query {query.status.lower()}: {query.error}."
                else:
                    answer.answer = (
                        "Local analytics supports telemetry/load, dispatch/commands, "
                        "and savings/ledger questions. No query was executed."
                    )
        except PermissionDenied:
            answer.status, answer.answer = (
                "REJECTED",
                "Permission to read this analytical domain is required.",
            )
        except Exception:
            answer.status = "UNAVAILABLE"
            answer.answer = (
                "AI provider or retrieval is unavailable. "
                "Local GridForge operations remain available."
            )
            answer.evidence = []
        with self.repo.lock, self.repo.db:
            self.require(principal, "ai.use")
            if write.conversation_id is None:
                self.repo.db.execute(
                    "INSERT INTO ai_conversations VALUES (?,?,?,?,?)",
                    (
                        str(answer.conversation_id),
                        str(self.repo.org_id),
                        str(self.repo.facility_id),
                        principal.actor,
                        answer.created_at.isoformat(),
                    ),
                )
            if query:
                self.repo.db.execute(
                    "INSERT INTO ai_queries VALUES (?,?,?)",
                    (
                        str(query.id),
                        str(answer.conversation_id),
                        query.model_dump_json(),
                    ),
                )
            self.repo.db.execute(
                "INSERT INTO ai_answers VALUES (?,?,?,?,?)",
                (
                    str(answer.id),
                    str(write.request_id),
                    fingerprint,
                    str(answer.conversation_id),
                    answer.model_dump_json(),
                ),
            )
            self.audit(
                "Copilot" + answer.status.title().replace("_", ""),
                answer.id,
                principal,
                write.request_id,
            )
        return answer

    def query(self, query_id: UUID, principal: Principal) -> QueryRun:
        self.require(principal, "ai.inspect")
        with self.repo.lock:
            row = self.repo.db.execute(
                "SELECT conversation_id,body FROM ai_queries WHERE id=?", (str(query_id),)
            ).fetchone()
            if not row:
                raise AIRejected("QUERY_NOT_FOUND")
            self.owner(UUID(row[0]), principal)
            query = QueryRun.model_validate_json(row[1])
            if query.source_view:
                self.require(principal, VIEW_PERMISSIONS[query.source_view])
            return query

    def feedback(self, write: FeedbackWrite, principal: Principal) -> FeedbackReceipt:
        self.require(principal, "ai.use")
        fingerprint = digest(write.model_dump(mode="json"))
        with self.repo.lock, self.repo.db:
            row = self.repo.db.execute(
                "SELECT conversation_id FROM ai_answers WHERE id=?", (str(write.answer_id),)
            ).fetchone()
            if not row:
                raise AIRejected("ANSWER_NOT_FOUND")
            self.owner(UUID(row[0]), principal)
            prior = self.repo.db.execute(
                "SELECT fingerprint,body FROM ai_feedback WHERE request_id=?",
                (str(write.request_id),),
            ).fetchone()
            if prior:
                if prior[0] != fingerprint:
                    raise AIRejected("IDEMPOTENCY_CONFLICT")
                return FeedbackReceipt.model_validate_json(prior[1])
            receipt = FeedbackReceipt(
                id=uuid4(),
                answer_id=write.answer_id,
                rating=write.rating,
                created_at=datetime.now(UTC),
            )
            self.repo.db.execute(
                "INSERT INTO ai_feedback VALUES (?,?,?,?,?,?)",
                (
                    str(receipt.id),
                    str(write.request_id),
                    fingerprint,
                    str(write.answer_id),
                    receipt.model_dump_json(),
                    write.note,
                ),
            )
            self.audit("CopilotFeedbackRecorded", receipt.id, principal, write.request_id)
            return receipt

    def snapshot(self, principal: Principal) -> CopilotSnapshot:
        self.require(principal, "ai.use")
        with self.repo.lock:
            documents = [
                KnowledgeDocument.model_validate_json(row[0]).model_copy(
                    update={"active": bool(row[1])}
                )
                for row in self.repo.db.execute(
                    "SELECT body,active FROM ai_documents WHERE org_id=? AND facility_id=? "
                    "ORDER BY rowid DESC LIMIT 100",
                    (str(self.repo.org_id), str(self.repo.facility_id)),
                )
            ]
            answers = [
                CopilotAnswer.model_validate_json(row[0])
                for row in self.repo.db.execute(
                    "SELECT a.body FROM ai_answers a JOIN ai_conversations c "
                    "ON c.id=a.conversation_id "
                    "WHERE c.org_id=? AND c.facility_id=? AND c.actor=? "
                    "ORDER BY a.rowid DESC LIMIT 20",
                    (str(self.repo.org_id), str(self.repo.facility_id), principal.actor),
                )
            ]
            visible = []
            for answer in answers:
                if answer.query_id:
                    row = self.repo.db.execute(
                        "SELECT body FROM ai_queries WHERE id=?", (str(answer.query_id),)
                    ).fetchone()
                    query = QueryRun.model_validate_json(row[0])
                    if (
                        query.source_view
                        and VIEW_PERMISSIONS[query.source_view] not in principal.permissions
                    ):
                        continue
                visible.append(answer)
        return CopilotSnapshot(
            provider=self.provider.name,
            embedding_model=EMBEDDING_MODEL,
            provider_state="READY" if self.provider.available else "UNAVAILABLE",
            retrieval_backend="PGVECTOR" if self.central_knowledge else "LOCAL",
            query_backend="POSTGRES_READ_ONLY" if self.query_dsn else "LOCAL_READ_ONLY",
            can_ingest="ai.ingest" in principal.permissions,
            can_inspect="ai.inspect" in principal.permissions,
            documents=documents,
            answers=visible,
            semantic_views=({"ai_telemetry": VIEWS["ai_telemetry"]} if self.query_dsn else VIEWS)
            if "ai.inspect" in principal.permissions
            else {},
        )
