import { useEffect, useRef, useState } from 'react';
import type {
  AskRequest,
  CopilotAnswer,
  CopilotSnapshot,
  DocumentWrite,
  QueryRun,
} from '@gridforge/api-client';
import { runtimeBridge } from '../lib/runtime';

export function Copilot({ desktop }: { desktop: boolean }) {
  const [data, setData] = useState<CopilotSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [question, setQuestion] = useState('');
  const [intent, setIntent] = useState<'KNOWLEDGE' | 'ANALYTICS'>('KNOWLEDGE');
  const [sql, setSql] = useState('');
  const [conversation, setConversation] = useState<string | null>(null);
  const [answer, setAnswer] = useState<CopilotAnswer | null>(null);
  const [query, setQuery] = useState<QueryRun | null>(null);
  const [key, setKey] = useState('');
  const [revision, setRevision] = useState(1);
  const [title, setTitle] = useState('');
  const [source, setSource] = useState('');
  const [text, setText] = useState('');
  const askRetry = useRef<AskRequest | null>(null);
  const documentRetry = useRef<DocumentWrite | null>(null);

  useEffect(() => {
    if (!desktop) return;
    let active = true;
    runtimeBridge
      .ai()
      .then((value) => {
        if (active) setData(value);
      })
      .catch(() => {
        if (active)
          setError(
            'Copilot status unavailable or permission denied. Core operations remain available.',
          );
      });
    return () => {
      active = false;
    };
  }, [desktop]);

  async function perform(work: () => Promise<void>) {
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      await work();
    } catch {
      setError(
        'Request failed or permission denied. Check System Health. Unchanged submissions reuse their request ID.',
      );
    } finally {
      setPending(false);
    }
  }

  if (!desktop)
    return (
      <section className="surface">
        <h2>Native desktop required</h2>
        <p>
          Knowledge and analytical answers use the authenticated facility
          runtime.
        </p>
      </section>
    );

  return (
    <div className="copilotPage">
      <section className="surface">
        <span className="simulationPill">SIMULATION · ADVISORY ONLY</span>
        <h2>Evidence-backed Copilot</h2>
        <p>
          Local retrieval quotes source documents. Analytics reads a bounded
          data snapshot. Answers never authorize dispatch.
        </p>
        <p>
          Provider: {data?.provider ?? 'Loading…'} ·{' '}
          {data?.provider_state ?? 'UNKNOWN'} · Embeddings:{' '}
          {data?.embedding_model ?? '—'}
        </p>
        <p>
          Retrieval: {data?.retrieval_backend ?? '—'} · Analytics:{' '}
          {data?.query_backend ?? '—'}
        </p>
        <p>
          The local baseline uses token matching, not a trained language model.
          Review document provenance and timestamps before acting.
        </p>
        {error && <p role="alert">{error}</p>}
        {notice && <p role="status">{notice}</p>}
        <button
          disabled={pending}
          onClick={() =>
            void perform(async () => {
              setData(await runtimeBridge.ai());
            })
          }
        >
          Refresh Copilot
        </button>
      </section>
      <section className="surface">
        <h2>Conversation</h2>
        <button
          disabled={pending}
          onClick={() => {
            setConversation(null);
            setAnswer(null);
            setQuery(null);
          }}
        >
          New conversation
        </button>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void perform(async () => {
              const body = {
                conversation_id: conversation,
                question,
                intent,
                sql: intent === 'ANALYTICS' && sql.trim() ? sql : null,
              };
              const previous = askRetry.current;
              const write =
                previous &&
                JSON.stringify({ ...previous, request_id: undefined }) ===
                  JSON.stringify(body)
                  ? previous
                  : { request_id: crypto.randomUUID(), ...body };
              askRetry.current = write;
              const result = await runtimeBridge.aiAsk(write);
              setAnswer(result);
              setConversation(result.conversation_id);
              setQuery(null);
              askRetry.current = null;
              setData(await runtimeBridge.ai());
            });
          }}
        >
          <label>
            Question type
            <select
              value={intent}
              disabled={pending}
              onChange={(event) =>
                setIntent(event.target.value as typeof intent)
              }
            >
              <option value="KNOWLEDGE">Knowledge documents</option>
              <option value="ANALYTICS">Analytics</option>
            </select>
          </label>
          <label>
            Question
            <textarea
              required
              maxLength={2000}
              value={question}
              disabled={pending}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="What does the shutdown SOP say? Or choose Analytics and ask for recent telemetry."
            />
          </label>
          {intent === 'ANALYTICS' && data?.can_inspect && (
            <details>
              <summary>Optional SQL · authorized query inspector</summary>
              <p>
                One SELECT from an allowlisted view. Maximum 100 result rows,
                latest 1,000 source rows, 200 ms execution budget.
              </p>
              <pre>{JSON.stringify(data.semantic_views, null, 2)}</pre>
              <label>
                SQL override
                <textarea
                  maxLength={4000}
                  value={sql}
                  disabled={pending}
                  onChange={(event) => setSql(event.target.value)}
                />
              </label>
            </details>
          )}
          <button disabled={pending || !data || !question.trim()}>
            {pending ? 'Working…' : 'Ask Copilot'}
          </button>
        </form>
        {answer && (
          <article className="copilotAnswer">
            <h3>
              {answer.status} · {answer.provider}
            </h3>
            <small>
              {new Date(answer.created_at).toLocaleString()} · Conversation{' '}
              {answer.conversation_id}
            </small>
            <p>
              <strong>{answer.question}</strong>
            </p>
            <pre>{answer.answer}</pre>
            {answer.evidence.map((item) => (
              <details key={item.chunk_id}>
                <summary>
                  [{item.citation}] {item.title} · revision {item.revision}
                </summary>
                <p>
                  Source: {item.source} · document {item.document_id} ·
                  characters {item.start}–{item.end}
                </p>
                <blockquote>{item.excerpt}</blockquote>
                <small>
                  SHA-256 {item.digest} · retrieval similarity {item.score}
                </small>
              </details>
            ))}
            {answer.query_id && data?.can_inspect && (
              <button
                disabled={pending}
                onClick={() =>
                  void perform(async () => {
                    setQuery(await runtimeBridge.aiQuery(answer.query_id!));
                  })
                }
              >
                Inspect query
              </button>
            )}
            <div className="copilotActions">
              {(['HELPFUL', 'NOT_HELPFUL'] as const).map((rating) => (
                <button
                  key={rating}
                  disabled={pending}
                  onClick={() =>
                    void perform(async () => {
                      await runtimeBridge.aiFeedback({
                        request_id: crypto.randomUUID(),
                        answer_id: answer.id,
                        rating,
                        note: '',
                      });
                      setNotice('Feedback recorded.');
                    })
                  }
                >
                  {rating === 'HELPFUL' ? 'Helpful' : 'Not helpful'}
                </button>
              ))}
            </div>
          </article>
        )}
        {query && (
          <section aria-label="Query inspector">
            <h3>Query inspector · {query.status}</h3>
            <p>
              Read-only · {query.row_limit} result rows ·{' '}
              {query.source_row_limit} source rows · {query.timeout_ms} ms ·{' '}
              {new Date(query.observed_at).toLocaleString()}
            </p>
            <pre>{query.proposed_sql}</pre>
            <pre>{query.executed_sql ?? query.error}</pre>
            <p>Server scope: {query.parameters.join(' / ')}</p>
            <pre>
              {JSON.stringify(
                { columns: query.columns, rows: query.rows },
                null,
                2,
              )}
            </pre>
            <small>Result digest {query.result_digest ?? 'None'}</small>
          </section>
        )}
        <h3>Recent answers</h3>
        {!data?.answers.length && <p>No conversations yet.</p>}
        {data?.answers.map((item) => (
          <button
            key={item.id}
            disabled={pending}
            onClick={() => {
              setConversation(item.conversation_id);
              setAnswer(item);
              setQuery(null);
            }}
          >
            {item.question} · {item.status}
          </button>
        ))}
      </section>
      <section className="surface">
        <h2>Knowledge library</h2>
        {data?.retrieval_backend === 'PGVECTOR' && (
          <p>
            Central retrieval is selected. This list shows local revisions; an
            administrator must publish them before they are available in central
            search.
          </p>
        )}
        <p>
          Import plain text or Markdown from a manual or SOP. Content is stored
          as source material, never executed. Revisions are immutable; retrieval
          uses only the current revision.
        </p>
        {!data?.documents.length && (
          <p>No knowledge documents have been ingested.</p>
        )}
        {data?.documents.map((doc) => (
          <article key={doc.id}>
            <strong>{doc.title}</strong> · {doc.document_key} v{doc.revision} ·{' '}
            {doc.active ? 'Current' : 'Superseded'}
            <p>
              {doc.source} · {doc.chunk_count} chunks ·{' '}
              {new Date(doc.created_at).toLocaleString()}
            </p>
          </article>
        ))}
        {data?.can_ingest && (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void perform(async () => {
                const body = {
                  document_key: key,
                  revision,
                  title,
                  source,
                  text,
                };
                const previous = documentRetry.current;
                const write =
                  previous &&
                  JSON.stringify({ ...previous, request_id: undefined }) ===
                    JSON.stringify(body)
                    ? previous
                    : { request_id: crypto.randomUUID(), ...body };
                documentRetry.current = write;
                await runtimeBridge.aiIngest(write);
                documentRetry.current = null;
                setData(await runtimeBridge.ai());
                setNotice('Knowledge revision ingested.');
              });
            }}
          >
            <label>
              Document key
              <input
                required
                pattern="[A-Za-z0-9_-]{1,64}"
                value={key}
                disabled={pending}
                onChange={(event) => setKey(event.target.value)}
              />
            </label>
            <label>
              Revision
              <input
                required
                type="number"
                min={1}
                max={10000}
                value={revision}
                disabled={pending}
                onChange={(event) => setRevision(Number(event.target.value))}
              />
            </label>
            <label>
              Title
              <input
                required
                maxLength={120}
                value={title}
                disabled={pending}
                onChange={(event) => setTitle(event.target.value)}
              />
            </label>
            <label>
              Source/reference
              <input
                required
                maxLength={200}
                value={source}
                disabled={pending}
                onChange={(event) => setSource(event.target.value)}
              />
            </label>
            <label>
              Document text
              <textarea
                required
                maxLength={20000}
                value={text}
                disabled={pending}
                onChange={(event) => setText(event.target.value)}
              />
            </label>
            <button disabled={pending || !text.trim()}>Ingest document</button>
          </form>
        )}
      </section>
    </div>
  );
}
