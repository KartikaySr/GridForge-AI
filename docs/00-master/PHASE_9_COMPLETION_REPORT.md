# Phase 9 completion report — advisory AI, RAG and diagnostics

Date: 2026-09-29. Phase 9 is complete for the simulation prototype. Phase 10 has not begun.

## 1. Implemented

Versioned knowledge ingestion, immutable document metadata/chunks, deterministic embeddings,
scoped retrieval, conversation persistence, provider abstraction, constrained Text-to-SQL,
allowlisted semantic views, read-only execution, budgets, source evidence, Copilot UI, authorized
query inspection, feedback and durable audit events. Optional PostgreSQL/pgvector adapters and
an explicit knowledge publication CLI are implemented and tested.

## 2. Files created

`services/ai/{__init__,contracts,providers,sql,service,postgres}.py`; SQLite migration
`0008_ai.sql`; central migrations `0003_ai_sync.sql`, `0004_ai_reporting.sql` and
`0005_ai_vectors.sql`; `scripts/publish_knowledge.py`; `Copilot.tsx` and its tests;
`tests/unit/test_ai.py`; `tests/integration/test_ai_postgres.py`; native generated
`ai_request.toml`; ADR 0010 and this report. The repository manifest lists full paths.

## 3. Files modified

Edge composition root, storage/read-only connection identity, scope permissions and stable
simulation actor; sync stream contracts, codec and receiver migrations; native capability,
bridge and explicit environment allowlist; desktop navigation, bridge and styles; generated
OpenAPI/TypeScript clients; dependency/lock files, Compose, configuration example, migration
regression expectations, README, development/configuration/API docs, context index and manifest.

## 4. Migrations

SQLite v7→v8 adds AI persistence, three semantic views and a seventh sync stream. The migration
preserves existing cursor values and conflict audit rows. Central migration 0003 adds the AI
stream to enrolled edges. Administrator migration 0004 provisions the restricted reader role
and scoped telemetry view; migration 0005 adds pgvector storage and forced RLS policies.

The actual local store was backed up to `.local/backups/edge-before-phase9.db` and upgraded to v8.
It preserved **42,100 telemetry rows, 42,100 telemetry outbox rows, 208 predictions, one optimization
run, zero dispatch commands, zero finance entries and zero sync conflicts**. Foreign-key checks
passed, and seven sync streams are present. No existing data was deleted.

## 5. APIs

Authenticated `/api/v1/ai` snapshot, `/ai/documents`, `/ai/ask`, `/ai/queries/{uuid}` and
`/ai/feedback`. Contracts reject caller-supplied scope and unknown fields. Server permissions
include `ai.use`, `ai.ingest`, `ai.inspect` and underlying analytics domain read permission.
Native `ai_request` exposes only five fixed operations and bounds request size. There is no AI
control/dispatch endpoint.

## 6. Events

Version-1 `edge.ai` events record knowledge ingestion, answer outcome and feedback with actor,
resource, scope, correlation, causation and idempotency references. The domain record and outbox
event commit together. Sync contains no prompts, document contents or SQL. The AI cursor uses
the existing replay/digest/acknowledgement boundary; real PostgreSQL tests verify its upload.

## 7. Tests created

29 Python unit cases cover 21 malicious SQL forms, scope and read-only execution, row/source/time
budgets, v7 cursor/conflict preservation, document revisions/citations/restart, conversation
ownership, idempotency/feedback, permission revocation, malicious document text, provider failure
and API authentication. Two PostgreSQL integration tests cover low-role permission denials,
scoped analytics, AI audit synchronization, real pgvector retrieval/RLS/revisions/replay and
multi-chunk CLI publication. Four frontend tests cover native-only access, safe text rendering,
permission-gated controls, unavailable state and query inspection. Existing native lifecycle tests
now read the real Copilot API and reject arbitrary AI operations.

## 8. Checks run

`npm run check`: Prettier/Ruff formatting, ESLint/Ruff, TypeScript, strict mypy, runtime/cloud
contract consistency, frontend/Python tests and production frontend build. `npm run native:check`:
rustfmt, warning-free Clippy and Rust tests. `npm run desktop:build`: native development executable
with embedded Phase 9 UI. Targeted AI/pgvector regression checks cover final source-construction
and multi-chunk publication refinements.

## 9. Results

**154 Python + 35 frontend + 3 native = 192 passing tests.** The full suite included real
PostgreSQL and pgvector checks on this macOS host. Four upstream deprecation warnings remain
non-failing. PostgreSQL tests skip without local PostgreSQL tools; vector tests additionally
need the extension or documented temporary compiled library. No remote CI/deployment result is
claimed. Native executable: `apps/desktop/src-tauri/target/debug/gridforge-desktop`.

## 10. Manual verification

Verified the actual v7→v8 local store upgrade and preserved counts after a backup. The native
supervisor tests exercise a real child runtime and its Copilot status API. Document ingestion,
retrieval, query execution, restart and failure flows were exercised through service/API tests;
frontend behavior through DOM tests. A manual GUI walkthrough is not claimed. No documents or
conversations were seeded into the user's local store, and no cloud credentials were configured.

## 11. Screens/features

AI Copilot shows provider/backend state, Knowledge versus Analytics questions, persistent recent
answers and conversation continuation, cited source revisions/offsets/hashes, query inspector,
feedback and a versioned knowledge library. Empty, unavailable and denied states are explicit.
The native UI displays SIMULATION and advisory-only labels. Document text is escaped, with no
HTML interpretation or embedded script execution.

## 12. Limitations

Default `local-extractive-v1` is a deterministic retrieval baseline, not a trained/generative
language model. Embeddings use lexical token hashing, not learned semantic embeddings. Plain
text/Markdown only; PDF/OCR is not implemented. Natural-language analytics maps to three local
query templates; authorized users can inspect or supply the restricted SELECT grammar. Central
analytics currently projects telemetry only. Central knowledge requires explicit publication;
its corpus is not automatically mirrored from local ingestion.

## 13. Simulations/mocks

All operational data and financial values remain SIMULATION. Frontend tests mock native IPC;
Python tests use real SQLite and PostgreSQL. A disabled provider exercises availability behavior.
Actual pgvector v0.8.0 C code was compiled in a temporary directory and loaded into temporary test
DBs without installing it globally. Production uses the normal CREATE EXTENSION migration.
No hosted LLM was called and no arbitrary provider-generated tool action was executed.

## 14. Technical debt

Hosted provider adapters, learned multilingual embeddings/retrieval evaluation, PDF/OCR,
production identity and credential vault integration, retention/archival, central enterprise
projections and corpus lifecycle UI remain future work. Exact vector search is sufficient for
this bounded prototype; approximate indexing and multi-site scale need measurements. Permission
denials still use the runtime's existing diagnostics; broader security-event hardening belongs
to Phase 10.

## 15. Security/safety

Provider interfaces have no machine-control capability. Source content cannot change permissions.
SQL is parsed before source replacement; only allowlisted views/columns/functions are admitted.
Scope is parameterized by trusted server identity before user filters/aggregates. SQLite uses a
separate query-only connection and authorizer. PostgreSQL executes as a restricted reader in a
read-only transaction, and knowledge uses forced RLS. Queries require domain permissions;
revocation also hides historical analytics and denies replay. Native credentials remain outside
UI/diagnostic DTOs. The simulation actor is stable per edge but does not represent authenticated
production personnel.

## 16. Performance/budgets

100 document revisions, 20,000 characters each; 1,000-character chunks with 100-character overlap;
256 embedding dimensions; four retrieval hits; 10,000 answers maximum. One answer-generation
request runs at a time. SQL caps at 100 result rows over the latest 1,000 scoped source rows,
200 ms execution budget and bounded connection/lock waits. Tests verify caps and interruption.
No claim of semantic retrieval accuracy, full-period reporting or production load capacity.

## 17. Documentation

README, context index, manifest, development/provisioning walkthrough, configuration/health,
API/event contracts, ADR 0010 and this report are updated. Optional DSNs and provider selection
are documented in `.env.example`. The native launcher now explicitly forwards those configured
sync/AI variables, correcting the prior environment-clearing integration gap.

## 18. Next phase / approval gate

Phase 10 is enterprise hardening: full RBAC/isolation, observability, security/audit hardening,
backup/recovery, performance, packaging/signing/update architecture, accessibility and regression.
**Awaiting explicit approval before starting Phase 10**, as required by the original phased plan.
