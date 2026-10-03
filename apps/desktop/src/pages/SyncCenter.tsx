import { useEffect, useState } from 'react';
import type { SyncSnapshot } from '@gridforge/api-client';
import { runtimeBridge } from '../lib/runtime';

export function SyncCenter({ desktop }: { desktop: boolean }) {
  const [data, setData] = useState<SyncSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [received, setReceived] = useState(0);
  useEffect(() => {
    if (!desktop) return;
    let active = true;
    const poll = async () => {
      try {
        const snapshot = await runtimeBridge.sync();
        if (active) {
          setData(snapshot);
          setReceived(Date.now());
          setError(null);
        }
      } catch {
        if (active)
          setError('Local sync status is unavailable. Check System Health.');
      }
    };
    void poll();
    const timer = setInterval(() => void poll(), 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [desktop]);
  if (!desktop)
    return (
      <section className="surface">
        <h2>Native desktop required</h2>
        <p>Cloud sync status comes from the authenticated local runtime.</p>
      </section>
    );
  const age = data?.oldest_pending_age_seconds;
  const date = (value: string) => new Date(value).toLocaleString();
  return (
    <div className="syncPage">
      <section className="surface">
        <span className="simulationPill">SIMULATION · ONE-WAY VISIBILITY</span>
        <h2>{data?.state ?? 'Loading sync status…'}</h2>
        <p>{data?.message ?? 'Reading durable local cursors.'}</p>
        <p>
          Local telemetry, forecasting, approval and simulated dispatch continue
          while cloud sync is offline. Cloud events never authorize a machine
          command.
        </p>
        {error && <p role="alert">{error}</p>}
        {received > 0 && (
          <small>
            Local status refreshed {new Date(received).toLocaleTimeString()}
          </small>
        )}
        {data && (
          <p>
            <strong>Edge ID</strong> {data.edge_id} · <strong>Facility</strong>{' '}
            {data.facility_id}
          </p>
        )}
        {!data?.configured && (
          <p>
            Cloud is not configured. An administrator must enroll this edge with
            the cloud receiver and supply its HTTPS endpoint and token through
            the native runtime environment.
          </p>
        )}
      </section>
      <section className="surface">
        <h2>Durable backlog</h2>
        <p>
          <strong>{data?.pending_count ?? '—'}</strong> events pending
          acknowledgement · oldest pending{' '}
          {age == null ? '—' : `${Math.floor(age)} seconds`} · unresolved
          conflicts {data?.conflict_count ?? '—'}
        </p>
        <p>
          Last successful acknowledgement:{' '}
          {data?.last_success_at ? date(data.last_success_at) : 'None'}
        </p>
        <p>
          Events are marked acknowledged only after PostgreSQL commits and the
          cloud returns a receipt. Local outbox rows are retained. A connection
          error does not discard or replay dispatch actions.
        </p>
      </section>
      <section className="surface">
        <h2>Stream cursors</h2>
        {data?.streams.map((stream) => (
          <article key={stream.stream}>
            <strong>{stream.stream}</strong> · {stream.pending_count} pending
            <p>
              Local {stream.local_last_sequence} · cloud acknowledged{' '}
              {stream.acknowledged_sequence} · oldest{' '}
              {stream.oldest_pending_at ? date(stream.oldest_pending_at) : '—'}
            </p>
            {stream.conflict_code && (
              <p role="alert">
                Quarantined: {stream.conflict_code}. Reconcile before resuming
                this stream.
              </p>
            )}
            {stream.last_error && !stream.conflict_code && (
              <p>{stream.last_error}</p>
            )}
          </article>
        ))}
      </section>
      {!!data?.conflicts.length && (
        <section className="surface">
          <h2>Conflict audit</h2>
          {data.conflicts.map((conflict) => (
            <article key={conflict.id}>
              <strong>{conflict.code}</strong> · {conflict.stream} #
              {conflict.sequence}
              <p>
                {conflict.detail} · {date(conflict.detected_at)}
              </p>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
