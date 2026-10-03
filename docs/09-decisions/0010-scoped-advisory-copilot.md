# ADR 0010 — scoped advisory Copilot

Status: accepted for Phase 9 simulation prototype, 2026-09-29.

## Provider and retrieval boundary

The default `local-extractive-v1` provider quotes evidence; it is not a trained language model.
`token-hash-256-v1` deterministically hashes lowercase alphanumeric tokens into a normalized
256-dimensional vector. This inexpensive lexical baseline supports offline operation, but has
collisions and no learned semantic understanding. Similarity is not calibrated confidence.
The `AdvisoryProvider` interface exposes only answer generation and SQL proposal generation.
It receives no database connection, credentials, dispatch service or tool executor. A disabled
or failed provider produces a persisted UNAVAILABLE answer; runtime health and control workers
remain independent.

Knowledge ingestion accepts bounded plain text/Markdown, a source reference, stable document
key and monotonically increasing revision. Immutable chunks retain exact character offsets,
content hashes and the embedding version. Current revisions alone participate in retrieval;
old evidence remains attached to old answers. Four matching chunks at most are quoted. Source
content is untrusted data and rendered as escaped text. No remote URLs, scripts or embedded
instructions are fetched or executed. PDF/OCR and hosted generative providers are not implemented.

## Persistence and scope

SQLite v8 stores documents/chunks, conversations, answers, query runs and feedback. Server-owned
organization/facility identity and principal permissions determine access. Conversations also
belong to an actor. The prototype's local actor is stable per edge, while each native session
still has a fresh credential and eight-hour expiry. This is not production user identity.

Every completed ingestion, answer (including unavailable/rejected outcomes) and feedback write
adds a same-transaction, version-1 `edge.ai` outbox event. The seventh sync stream carries only
actor/resource/correlation references and outcome, never document text, SQL or prompts. Full
knowledge publication is an explicit administrator command. Sync receiver migration 0003 adds
the AI cursor to enrolled edges while preserving earlier cursors. Old six-stream receivers must
be upgraded before v8 edges can reconcile.

## SQL boundary

SQLGlot parses a deliberately small SELECT grammar. DDL/DML, multiple statements, comments,
joins, CTEs, subqueries, schema-qualified tables, arbitrary functions and hidden columns are
rejected. Only three local semantic views are available: telemetry, dispatch state and savings
ledger. Monetary values remain exact strings; aggregate money arithmetic is rejected.

After validation, code replaces the source with a parameterized org/facility-scoped query over
the latest 1,000 rows. User predicates cannot widen this scope. Results cap at 100 rows; SQLite
uses a separate connection, query_only, a restrictive authorizer, a 100 ms lock timeout and a
200 ms progress budget. Base-table reads are allowed only through the trusted view definition.
The query inspector records the proposal, final scoped SQL, parameters, timestamp, limits,
result hash and rejected/unavailable outcome. Inspection additionally requires `ai.inspect`;
analytics requires the underlying telemetry/dispatch/finance read permission. Revoking a domain
permission hides its prior answers and prevents their idempotent replay.

Central telemetry analytics uses the separate `gridforge_ai_reader` role, SELECT-only grants on
an allowlisted security-barrier view, a READ ONLY transaction and statement timeout. SQL parsing
and trusted scope still apply. Central dispatch/financial projections are not available: synced
events do not contain enough information to invent these views.

## PostgreSQL and pgvector

Migration 0004 provisions the reporting role/view; 0005 provisions vector(256) chunks, scoped
metadata and forced row-level policies. A separate knowledge writer role handles explicit
publication; the desktop receives only reader DSNs. `PgVectorKnowledge` uses exact cosine search
and immutable revision/replay checks. Approximate indexing is deferred until measured volume
justifies it. Optional central query and retrieval adapters fail visibly if unavailable; they
never silently switch data sources. Default local retrieval requires no PostgreSQL or network.

Native configuration forwards only five named sync/AI variables after clearing the environment.
Reader credentials never cross the WebView bridge. OS credential storage and production role
administration remain Phase 10 hardening work.

## Evidence

Tests cover malicious SQL, scope escape, prompt-like document content, replay, revision handling,
conversation ownership, permission revocation, budget limits, provider outage, restart persistence,
existing sync-conflict migration, real PostgreSQL role denial and real pgvector/RLS retrieval.
The parser and cosine-query implementation follow [SQLGlot](https://sqlglot.com/) and
[pgvector](https://github.com/pgvector/pgvector) primary documentation.
