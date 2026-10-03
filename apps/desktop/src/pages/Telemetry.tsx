import type { HistoryPage } from '@gridforge/api-client';
import { useState } from 'react';
import { StatusBadge } from '../components/StatusBadge';
import {
  hasFreshHealth,
  runtimeBridge,
  type RuntimeSnapshot,
} from '../lib/runtime';

export function Telemetry({
  snapshot,
  desktop,
}: {
  snapshot: RuntimeSnapshot;
  desktop: boolean;
}) {
  const [asset, setAsset] = useState('all');
  const [history, setHistory] = useState<HistoryPage | null>(null);
  const [loading, setLoading] = useState(false);
  async function older() {
    setLoading(true);
    try {
      const before = history
        ? history.next_cursor
        : (data?.recent.at(-1)?.row_id ?? null);
      setHistory(
        await runtimeBridge.history(before, asset === 'all' ? null : asset),
      );
    } catch {
      setNotice('History unavailable. Check runtime health and retry.');
    } finally {
      setLoading(false);
    }
  }
  const [notice, setNotice] = useState('');
  const [pending, setPending] = useState(false);
  const data = snapshot.telemetry;
  const connected =
    hasFreshHealth(snapshot) &&
    snapshot.telemetry_checked_ms != null &&
    Date.now() >= snapshot.telemetry_checked_ms &&
    Date.now() - snapshot.telemetry_checked_ms < 5000;
  async function scenario(value: string) {
    setPending(true);
    try {
      await runtimeBridge.scenario(value);
      setNotice(
        'Scenario requested. The current scenario below confirms application.',
      );
    } catch {
      setNotice('Scenario request failed. Check runtime health and retry.');
    } finally {
      setPending(false);
    }
  }
  if (!data)
    return (
      <section className="surface">
        <h2>Synthetic factory telemetry</h2>
        <p>
          {desktop
            ? 'Waiting for the authenticated simulator stream…'
            : 'Open the native desktop to receive live simulator telemetry.'}
        </p>
        <p className="muted">
          No measurements are fabricated in browser preview.
        </p>
      </section>
    );
  const live =
    connected &&
    data.assets.length > 0 &&
    data.assets.every((item) => item.status === 'LIVE');
  const total = data.assets.reduce(
    (sum, item) => sum + (item.point?.value ?? 0),
    0,
  );
  const formatTime = (value: string) =>
    new Intl.DateTimeFormat('en-GB', {
      timeZone: data.timezone,
      dateStyle: 'short',
      timeStyle: 'medium',
    }).format(new Date(value));
  const rows = (history?.points ?? data.recent).filter(
    (point) => asset === 'all' || point.asset_id === asset,
  );
  const series = [...rows]
    .reverse()
    .filter((point) => point.quality === 'GOOD' && point.flags.length === 0);
  const max = Math.max(1, ...series.map((point) => point.value));
  return (
    <>
      <section className="surface telemetryToolbar">
        <div>
          <span className="eyebrow">
            SIMULATED · {data.facility_name} · {data.timezone}
          </span>
          <h2>
            Factory telemetry{' '}
            <StatusBadge
              state={connected ? data.worker_state : 'DISCONNECTED'}
            />
          </h2>
          <p>
            Seed {data.seed} · Tick {data.tick} · Current scenario:{' '}
            <strong>{data.scenario}</strong>
          </p>
        </div>
        <label>
          Simulation scenario
          <select
            aria-label="Simulation scenario"
            value={data.scenario}
            disabled={!connected || pending || snapshot.busy}
            onChange={(event) => void scenario(event.target.value)}
          >
            {['normal', 'spike', 'bad', 'stale', 'disconnected'].map(
              (value) => (
                <option key={value}>{value}</option>
              ),
            )}
          </select>
        </label>
        {notice && <p role="status">{notice}</p>}
      </section>
      {!connected && (
        <p className="runtimeBanner" role="alert">
          Stream disconnected. Showing last known data; reconnect is automatic.
        </p>
      )}
      {data.storage_full && (
        <p className="runtimeBanner" role="alert">
          Storage capacity reached. New measurements are rejected; retained
          telemetry and pending outbox are preserved.
        </p>
      )}
      <section className="overviewGrid telemetrySummary">
        <div className="metric">
          <span>SIMULATED TOTAL LOAD</span>
          <strong>{live ? total.toFixed(1) + ' kW' : 'Unavailable'}</strong>
          <small>
            {live
              ? 'All registered assets fresh and good'
              : 'Requires all registered assets live and good'}
          </small>
        </div>
        <div className="metric">
          <span>INGESTED / DUPLICATES</span>
          <strong>
            {data.accepted} / {data.duplicates}
          </strong>
          <small>Durable counters</small>
        </div>
        <div className="metric">
          <span>REJECTED / BACKPRESSURE</span>
          <strong>
            {data.rejected} / {data.backpressure}
          </strong>
          <small>
            Queue {data.queue_depth} / {data.queue_capacity} batches
          </small>
        </div>
        <div className="metric">
          <span>PENDING OUTBOX</span>
          <strong>{data.pending_outbox}</strong>
          <small>
            Cloud acknowledgement shown in Sync Center · capacity{' '}
            {data.storage_capacity}
          </small>
        </div>
      </section>
      <section className="surface">
        <div className="sectionHeader">
          <h2>Asset state</h2>
          <span className="muted">Source: SIMULATOR · active power</span>
        </div>
        <div className="telemetryAssets">
          {data.assets.map((item) => (
            <article key={item.asset_id} className="metric">
              <span>
                {item.asset_id} · {item.label}
              </span>
              <StatusBadge state={connected ? item.status : 'DISCONNECTED'} />
              <strong>
                {item.point ? item.point.value.toFixed(1) + ' kW' : '—'}
              </strong>
              <small>
                {item.status !== 'LIVE' || !connected
                  ? 'Last known sample · '
                  : ''}
                {item.point
                  ? formatTime(item.point.event_time)
                  : 'No sample yet'}
              </small>
              <small>
                {item.point?.flags.join(', ') || item.point?.quality}
              </small>
            </article>
          ))}
        </div>
      </section>
      <section className="surface">
        <div className="sectionHeader">
          <div>
            <span className="eyebrow">TELEMETRY EXPLORER</span>
            <h2>Recent durable measurements</h2>
          </div>
          <label>
            Asset{' '}
            <select
              aria-label="Filter telemetry asset"
              value={asset}
              disabled={loading}
              onChange={(event) => {
                setAsset(event.target.value);
                setHistory(null);
              }}
            >
              <option value="all">All assets</option>
              {data.assets.map((item) => (
                <option key={item.asset_id} value={item.asset_id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="muted">
          {history ? 'Historical page' : 'Latest 100 stored points'} · newest
          first · {data.timezone} · canonical kW.
        </p>
        {asset !== 'all' && (
          <svg
            className="telemetryChart"
            viewBox="0 0 800 130"
            role="img"
            aria-label="Recent good active power samples, kW"
          >
            <polyline
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              points={series
                .map(
                  (point, i) =>
                    `${(i * 800) / Math.max(1, series.length - 1)},${120 - (point.value / max) * 110}`,
                )
                .join(' ')}
            />
            <text x="8" y="16" fill="currentColor">
              {max.toFixed(0)} kW · good samples only
            </text>
          </svg>
        )}
        <div className="telemetryPagination">
          <button
            className="secondary"
            disabled={
              !connected ||
              loading ||
              (history
                ? history.next_cursor === null
                : data.recent.length < 100)
            }
            onClick={() => void older()}
          >
            {loading ? 'Loading history…' : 'Older measurements'}
          </button>
          {history && (
            <button
              className="secondary"
              disabled={loading}
              onClick={() => setHistory(null)}
            >
              Return to live
            </button>
          )}
        </div>
        <div className="telemetryTable">
          <table>
            <thead>
              <tr>
                <th>Asset</th>
                <th>Event time ({data.timezone})</th>
                <th>kW</th>
                <th>Quality / flags</th>
                <th>Sequence</th>
                <th>Received ({data.timezone})</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((point) => (
                <tr key={point.row_id}>
                  <td>{point.asset_id}</td>
                  <td>{formatTime(point.event_time)}</td>
                  <td>{point.value.toFixed(2)}</td>
                  <td>{[point.quality, ...point.flags].join(' · ')}</td>
                  <td>{point.sequence}</td>
                  <td>{formatTime(point.received_time)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <p>No stored measurements match this asset.</p>}
        </div>
      </section>
    </>
  );
}
