import { useEffect, useRef, useState } from 'react';
import type {
  Incident,
  IncidentAction,
  IncidentSnapshot,
} from '@gridforge/api-client';
import { runtimeBridge } from '../lib/runtime';

export function Incidents({ desktop }: { desktop: boolean }) {
  const [snapshot, setSnapshot] = useState<IncidentSnapshot | null>(null);
  const [allowed, setAllowed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [note, setNote] = useState('');
  const pending = useRef<IncidentAction | null>(null);
  async function refresh(before: number | null = null) {
    setBusy(true);
    try {
      const [data, identity] = await Promise.all([
        runtimeBridge.incidents(before),
        runtimeBridge.identity(),
      ]);
      setSnapshot(data);
      setAllowed(identity.permissions.includes('alert.manage'));
      setMessage('');
    } catch {
      setMessage('Incident history unavailable. Check sign-in and runtime.');
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (!desktop) return;
    let active = true;
    void Promise.all([runtimeBridge.incidents(), runtimeBridge.identity()])
      .then(([data, identity]) => {
        if (active) {
          setSnapshot(data);
          setAllowed(identity.permissions.includes('alert.manage'));
        }
      })
      .catch(() => {
        if (active)
          setMessage('Incident history unavailable. Refresh to retry.');
      });
    return () => {
      active = false;
    };
  }, [desktop]);
  async function act(incident: Incident, action: 'acknowledge' | 'resolve') {
    const prior = pending.current;
    const write: IncidentAction =
      prior &&
      prior.incident_id === incident.id &&
      prior.expected_revision === incident.revision &&
      prior.action === action &&
      prior.note === note
        ? prior
        : {
            request_id: crypto.randomUUID(),
            incident_id: incident.id,
            expected_revision: incident.revision,
            action,
            note,
          };
    pending.current = write;
    setBusy(true);
    try {
      await runtimeBridge.incidentAction(write);
      pending.current = null;
      await refresh();
    } catch {
      setMessage(
        'Action rejected or unavailable. Retry unchanged inputs safely; refresh if the incident revision changed.',
      );
    } finally {
      setBusy(false);
    }
  }
  if (!desktop)
    return (
      <section className="surface">
        <h2>Alerts & Incidents</h2>
        <p>Open the native desktop for incident history.</p>
      </section>
    );
  return (
    <section className="surface">
      <h2>Demand-risk incidents · SIMULATION</h2>
      <p>
        Local-only history. Acknowledgement records investigation, never
        dispatch approval. Closing a superseded risk does not establish that
        demand is safe. Use Forecasting & Risk for current evidence.
      </p>
      <button disabled={busy} onClick={() => void refresh()}>
        Refresh newest incidents
      </button>
      <p role="status">{message}</p>
      {snapshot && (
        <p>
          As of {snapshot.observed_at} · {snapshot.total} incidents ·{' '}
          {snapshot.pending_events} source events pending ·{' '}
          {snapshot.worker_error ?? 'Incident processor healthy'}
        </p>
      )}
      {allowed && (
        <label>
          Investigation note
          <textarea
            maxLength={500}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </label>
      )}
      {snapshot?.incidents.length === 0 && (
        <p>No demand-risk incidents recorded.</p>
      )}
      {snapshot?.incidents.map((i) => (
        <article className="reportEntry" key={i.id}>
          <h3>
            {i.status} · source {i.source_state}
          </h3>
          <p>
            Forecast peak {i.predicted_peak_kw} kW · threshold {i.threshold_kw}{' '}
            kW
          </p>
          <p>
            Opened {i.opened_at} · Updated {i.updated_at} · Revision{' '}
            {i.revision}
          </p>
          <p>
            Risk {i.risk_id} · Prediction {i.prediction_id}
          </p>
          {i.note && (
            <p>
              {i.actor}: {i.note}
            </p>
          )}
          {allowed && (
            <div>
              <button
                disabled={busy || !note.trim() || i.status !== 'OPEN'}
                onClick={() => void act(i, 'acknowledge')}
              >
                Acknowledge
              </button>
              <button
                disabled={
                  busy ||
                  !note.trim() ||
                  i.status !== 'ACKNOWLEDGED' ||
                  i.source_state === 'OPEN'
                }
                onClick={() => void act(i, 'resolve')}
              >
                Close reviewed incident
              </button>
            </div>
          )}
        </article>
      ))}
      {snapshot?.next_before && (
        <button
          disabled={busy}
          onClick={() => void refresh(snapshot.next_before)}
        >
          Older incidents
        </button>
      )}
    </section>
  );
}
