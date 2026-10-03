from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from edge.runtime.contracts import Contract


class DocumentWrite(Contract):
    request_id: UUID
    document_key: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    revision: int = Field(ge=1, le=10000)
    title: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=20000)


class KnowledgeDocument(Contract):
    id: UUID
    document_key: str
    revision: int
    title: str
    source: str
    org_id: UUID
    facility_id: UUID
    digest: str
    created_at: datetime
    chunk_count: int
    embedding_model: str
    active: bool


class Evidence(Contract):
    citation: str
    document_id: UUID
    revision: int
    title: str
    source: str
    chunk_id: UUID
    start: int
    end: int
    digest: str
    excerpt: str
    score: float


class AskRequest(Contract):
    request_id: UUID
    conversation_id: UUID | None = None
    question: str = Field(min_length=1, max_length=2000)
    intent: Literal["KNOWLEDGE", "ANALYTICS"] = "KNOWLEDGE"
    sql: str | None = Field(default=None, min_length=1, max_length=4000)


class QueryRun(Contract):
    id: UUID
    status: Literal["SUCCEEDED", "REJECTED", "UNAVAILABLE"]
    proposed_sql: str
    executed_sql: str | None
    parameters: list[str]
    columns: list[str]
    rows: list[list[str | int | float | None]]
    row_limit: int = 100
    source_row_limit: int = 1000
    timeout_ms: int = 200
    source_view: str | None
    observed_at: datetime
    error: str | None
    result_digest: str | None


class CopilotAnswer(Contract):
    id: UUID
    request_id: UUID
    conversation_id: UUID
    question: str
    answer: str
    status: Literal["ANSWERED", "NO_EVIDENCE", "REJECTED", "UNAVAILABLE"]
    provider: str
    created_at: datetime
    evidence: list[Evidence]
    query_id: UUID | None
    mode: Literal["SIMULATION"] = "SIMULATION"
    advisory_only: Literal[True] = True


class FeedbackWrite(Contract):
    request_id: UUID
    answer_id: UUID
    rating: Literal["HELPFUL", "NOT_HELPFUL"]
    note: str = Field(default="", max_length=500)


class FeedbackReceipt(Contract):
    id: UUID
    answer_id: UUID
    rating: Literal["HELPFUL", "NOT_HELPFUL"]
    created_at: datetime


class CopilotSnapshot(Contract):
    provider: str
    embedding_model: str
    provider_state: Literal["READY", "UNAVAILABLE"]
    retrieval_backend: Literal["LOCAL", "PGVECTOR"] = "LOCAL"
    query_backend: Literal["LOCAL_READ_ONLY", "POSTGRES_READ_ONLY"] = "LOCAL_READ_ONLY"
    advisory_only: Literal[True] = True
    mode: Literal["SIMULATION"] = "SIMULATION"
    can_ingest: bool
    can_inspect: bool
    documents: list[KnowledgeDocument]
    answers: list[CopilotAnswer]
    semantic_views: dict[str, list[str]]
