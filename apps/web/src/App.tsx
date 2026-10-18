import { Evidence } from './components/Evidence';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity,
  ArrowRight,
  Building2,
  ChevronDown,
  Database,
  LogOut,
  RefreshCw,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import type {
  PortalHistory,
  PortalIdentity,
  Portfolio,
} from '@gridforge/api-client';
import { api, ApiError } from './api';
const streams = [
  ['telemetry', 'Telemetry'],
  ['registry', 'Assets & configuration'],
  ['intelligence', 'Forecasts & risk'],
  ['optimization', 'Proposals'],
  ['dispatch', 'Dispatch history'],
  ['finance', 'Verification & savings'],
  ['ai', 'Advisory audit'],
] as const;
function scalar(value: unknown): string {
  return ['string', 'number', 'boolean'].includes(typeof value)
    ? String(value)
    : '—';
}
export function App() {
  const [user, setUser] = useState<PortalIdentity | null>(null),
    [checking, setChecking] = useState(true);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null),
    [history, setHistory] = useState<PortalHistory | null>(null);
  const [edge, setEdge] = useState(''),
    [stream, setStream] = useState('telemetry');
  const [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(''),
    [clock, setClock] = useState(Date.now);
  const generation = useRef(0);
  const clear = useCallback(() => {
    generation.current++;
    setUser(null);
    setPortfolio(null);
    setHistory(null);
    setEdge('');
  }, []);
  const failure = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 401) {
        clear();
        setNotice('Your session ended. Sign in again.');
      } else {
        if (error instanceof ApiError && [403, 404].includes(error.status)) {
          generation.current++;
          setHistory(null);
          setPortfolio(null);
          setEdge('');
        }
        setNotice(
          'Connection unavailable or access changed. Refresh to retry; displayed records are historical.',
        );
      }
    },
    [clear],
  );
  useEffect(() => {
    let active = true;
    void api
      .me()
      .then((u) => {
        if (active) setUser(u);
      })
      .catch(() => {})
      .finally(() => {
        if (active) setChecking(false);
      });
    const timer = setInterval(() => setClock(Date.now()), 1000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);
  useEffect(() => {
    if (!user) return;
    let active = true;
    void api
      .portfolio()
      .then((p) => {
        if (active) {
          setPortfolio(p);
          setEdge(p.facilities[0]?.edge_id ?? '');
        }
      })
      .catch((error) => {
        if (active) failure(error);
      });
    return () => {
      active = false;
    };
  }, [user, failure]);
  useEffect(() => {
    if (!user || !edge) return;
    let active = true;
    const key = ++generation.current;
    setHistory(null);
    void api
      .history(edge, stream)
      .then((h) => {
        if (active && generation.current === key) setHistory(h);
      })
      .catch((e) => {
        if (active && generation.current === key) failure(e);
      });
    return () => {
      active = false;
    };
  }, [user, edge, stream, failure]);
  async function refresh(before: number | null = null) {
    const key = ++generation.current;
    setBusy(true);
    setNotice('');
    try {
      const p = await api.portfolio();
      const h = edge ? await api.history(edge, stream, before) : null;
      if (generation.current === key) {
        setPortfolio(p);
        setHistory(h);
        if (!edge) setEdge(p.facilities[0]?.edge_id ?? '');
      }
    } catch (e) {
      if (generation.current === key) failure(e);
    } finally {
      setBusy(false);
    }
  }
  const selected = portfolio?.facilities.find((f) => f.edge_id === edge);
  const receiptAge = selected?.last_received_at
    ? clock - Date.parse(selected.last_received_at)
    : Infinity;
  const freshness =
    receiptAge >= 0 && receiptAge <= 30000
      ? 'Recent receipt'
      : selected?.last_received_at
        ? 'Stale receipt'
        : 'No received data';
  if (!user)
    return (
      <div className="loginShell">
        <section className="loginStory">
          <div className="brand">
            <Zap /> GRIDFORGE <b>AI</b>
          </div>
          <p className="eyebrow">ENTERPRISE / WEB PROTOTYPE</p>
          <h1>
            One view.
            <br />
            Every energy
            <br />
            <em>decision.</em>
          </h1>
          <p>
            Follow the evidence from factory telemetry to verified simulation
            outcomes. Built for the people overseeing the whole operation.
          </p>
          <div className="trust">
            <ShieldCheck /> Read-only access · Facility scoped · Simulation
          </div>
        </section>
        <main className="loginCard">
          <p className="eyebrow">WELCOME BACK</p>
          <h2>Sign in to your workspace</h2>
          <p>
            Use your provisioned web account. Desktop credentials are managed
            separately.
          </p>
          {checking ? (
            <p role="status">Checking session…</p>
          ) : (
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                const form = e.currentTarget;
                const data = new FormData(form);
                setBusy(true);
                setNotice('');
                try {
                  setUser(
                    await api.login(
                      String(data.get('username')),
                      String(data.get('password')),
                    ),
                  );
                  form.reset();
                } catch {
                  setNotice(
                    'Sign-in unavailable. Check your credentials or try again shortly.',
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              <label>
                Username
                <input
                  name="username"
                  autoComplete="username"
                  required
                  maxLength={64}
                />
              </label>
              <label>
                Password
                <input
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  minLength={12}
                  maxLength={128}
                />
              </label>
              <button disabled={busy}>
                Enter workspace <ArrowRight size={17} />
              </button>
            </form>
          )}
          <p role="status">{notice}</p>
          <small>
            No public registration. Ask your administrator for facility access.
          </small>
        </main>
      </div>
    );
  return (
    <div className="portal">
      <a className="skip" href="#content">
        Skip to content
      </a>
      <aside>
        <div className="brand">
          <Zap /> GRIDFORGE <b>AI</b>
        </div>
        <p className="eyebrow">ENTERPRISE WORKSPACE</p>
        <div className="workspaceLabel">
          <Building2 /> Facility intelligence
        </div>
        <nav aria-label="Evidence streams">
          {streams.map(([id, label]) => (
            <button
              key={id}
              className={stream === id ? 'active' : ''}
              aria-current={stream === id ? 'page' : undefined}
              onClick={() => {
                setStream(id);
                setNotice('');
              }}
            >
              {label}
              <ArrowRight size={14} />
            </button>
          ))}
        </nav>
        <div className="asideFoot">
          <ShieldCheck size={18} />
          <p>
            Simulation environment
            <br />
            <small>View evidence. Authority stays at the edge.</small>
          </p>
        </div>
      </aside>
      <div className="mainColumn">
        <header>
          <span>
            Portfolio <span className="muted">/ Evidence workspace</span>
          </span>
          <div>
            <span className="pill">SIMULATION</span>
            <span>{user.username}</span>
            <button
              className="iconButton"
              aria-label="Sign out"
              onClick={async () => {
                setBusy(true);
                try {
                  await api.logout();
                  clear();
                  setNotice('Signed out.');
                } catch {
                  setNotice(
                    'Sign-out could not be confirmed. Retry before leaving this device.',
                  );
                } finally {
                  setBusy(false);
                }
              }}
              disabled={busy}
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>
        <main id="content">
          <div className="pageTitle">
            <div>
              <p className="eyebrow">VISIBILITY WITH TRACEABILITY</p>
              <h1>{streams.find((s) => s[0] === stream)?.[1]}</h1>
              <p>Received evidence across your authorized facilities.</p>
            </div>
            <button
              className="secondary"
              disabled={busy}
              onClick={() => void refresh()}
            >
              <RefreshCw size={16} /> Refresh newest
            </button>
          </div>
          <div className="summaryGrid">
            <article>
              <Building2 />
              <span>AUTHORIZED EDGES</span>
              <strong>{portfolio?.facilities.length ?? '—'}</strong>
              <small>Up to {portfolio?.limit ?? 100} per portfolio</small>
            </article>
            <article>
              <Activity />
              <span>SELECTED EDGE RECEIPT</span>
              <strong>{freshness}</strong>
              <small>Receipt freshness is not live plant status</small>
            </article>
            <article>
              <Database />
              <span>VISIBLE RECORDS</span>
              <strong>{history?.events.length ?? '—'}</strong>
              <small>Bounded page · newest first</small>
            </article>
          </div>
          <section className="evidence">
            <div className="evidenceHeader">
              <div>
                <label htmlFor="facility">Facility / edge</label>
                <div className="selectWrap">
                  <select
                    id="facility"
                    value={edge}
                    onChange={(e) => setEdge(e.target.value)}
                  >
                    <option value="">Select an authorized facility</option>
                    {portfolio?.facilities.map((f) => (
                      <option key={f.edge_id} value={f.edge_id}>
                        {f.facility_id} · {f.edge_id.slice(0, 8)}
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={16} />
                </div>
              </div>
              <span className="pill muted">
                {selected?.enabled === false ? 'EDGE DISABLED' : 'READ ONLY'}
              </span>
            </div>
            {selected && (
              <div className="scopeLine">
                Organization {selected.org_id} · Last receipt{' '}
                {selected.last_received_at ?? 'none'}
                <br />
                Portal snapshot {portfolio?.observed_at}. Source timestamps and
                quality are preserved in each record.
              </div>
            )}
            <p role="status" className="notice">
              {notice}
            </p>
            {portfolio?.facilities.length === 0 && (
              <div className="empty">
                <Building2 />
                <h2>No facilities assigned</h2>
                <p>
                  An administrator must grant membership to an enrolled
                  facility.
                </p>
              </div>
            )}
            {edge && !history && !notice && (
              <p className="empty" role="status">
                Loading received history…
              </p>
            )}
            {history?.events.length === 0 && (
              <div className="empty">
                <Database />
                <h2>No synchronized records yet</h2>
                <p>
                  Start the desktop and configure its cloud sync to populate
                  this stream.
                </p>
              </div>
            )}
            {history?.events.map((event) => {
              return (
                <article className="eventCard" key={event.event_id}>
                  <div className="eventHeading">
                    <h2>{event.event_type}</h2>
                    <span className="pill">#{event.sequence}</span>
                  </div>
                  <Evidence event={event} />
                  <p className="timestamps">
                    Source: {scalar(event.body.occurred_at)} · Received:{' '}
                    {event.received_at}
                  </p>
                  <details>
                    <summary>Inspect event evidence and identifiers</summary>
                    <pre>{JSON.stringify(event.body, null, 2)}</pre>
                  </details>
                </article>
              );
            })}
            {history?.next_before && (
              <button
                className="secondary"
                disabled={busy}
                onClick={() => void refresh(history.next_before)}
              >
                Older records
              </button>
            )}
          </section>
          <footer>
            Prototype visibility only. Local production reports and incident
            workflow records are not synchronized. Financial values remain
            synthetic; no physical control or utility settlement.
          </footer>
        </main>
      </div>
    </div>
  );
}
