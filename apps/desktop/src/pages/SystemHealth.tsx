import { StatusBadge } from '../components/StatusBadge';
import { hasFreshHealth, type RuntimeSnapshot } from '../lib/runtime';

export function SystemHealth({
  snapshot,
  desktop,
  pending,
  act,
  actionError,
}: {
  snapshot: RuntimeSnapshot;
  desktop: boolean;
  pending: boolean;
  act: (action: 'restart' | 'stop') => Promise<void>;
  actionError: string | null;
}) {
  const fresh = hasFreshHealth(snapshot);
  return (
    <>
      <section className="surface">
        <div className="sectionHeader">
          <div>
            <span className="eyebrow">SUPERVISED LOCAL PROCESS</span>
            <h2>Runtime lifecycle</h2>
          </div>
          <StatusBadge
            state={
              snapshot.state === 'READY' && !fresh ? 'STALE' : snapshot.state
            }
          />
        </div>
        <p role="status">{snapshot.message}</p>
        <div className="buttonRow">
          <button
            disabled={!desktop || pending}
            onClick={() => void act('restart')}
          >
            {pending
              ? 'Operation in progress…'
              : snapshot.state === 'STOPPED'
                ? 'Start runtime'
                : 'Restart runtime'}
          </button>
          <button
            className="secondary"
            disabled={
              !desktop ||
              pending ||
              ['STOPPED', 'FAILED', 'UNAVAILABLE'].includes(snapshot.state)
            }
            onClick={() => void act('stop')}
          >
            Stop runtime
          </button>
        </div>
        {actionError && (
          <p role="alert" className="errorText">
            {actionError}
          </p>
        )}
        <dl className="keyValues">
          <dt>Launch generation</dt>
          <dd>{snapshot.generation}</dd>
          <dt>Process ID</dt>
          <dd>{snapshot.pid ?? 'Not running'}</dd>
          <dt>Instance</dt>
          <dd className="mono">{snapshot.instance_id ?? 'Not started'}</dd>
          <dt>Last successful health check (UTC)</dt>
          <dd>
            {snapshot.last_checked_ms
              ? new Date(snapshot.last_checked_ms).toISOString()
              : 'No successful check'}
          </dd>
          <dt>Readiness scope</dt>
          <dd>
            {snapshot.health?.readiness_scope === 'telemetry'
              ? 'Simulation telemetry · operational workflows unavailable'
              : 'Shell API only · operational workflows unavailable'}
          </dd>
        </dl>
      </section>
      <section className="surface">
        <h2>Component health</h2>
        {fresh && snapshot.health ? (
          <table>
            <thead>
              <tr>
                <th>Component</th>
                <th>State</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.health.components.map((component) => (
                <tr key={component.name}>
                  <td>{component.name}</td>
                  <td>
                    <StatusBadge state={component.state} />
                  </td>
                  <td>{component.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="emptyState">
            Current component health is unavailable. Start or recover the
            runtime to inspect it.
          </div>
        )}
      </section>
      <section className="surface">
        <h2>
          Lifecycle history <small>Current desktop session · UTC</small>
        </h2>
        {snapshot.events.length ? (
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>State</th>
                <th>Generation</th>
              </tr>
            </thead>
            <tbody>
              {[...snapshot.events].reverse().map((event, index) => (
                <tr key={`${event.timestamp_ms}-${index}`}>
                  <td className="mono">
                    {new Date(event.timestamp_ms).toISOString()}
                  </td>
                  <td>{event.event}</td>
                  <td>{event.generation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="emptyState">No lifecycle events yet.</div>
        )}
      </section>
    </>
  );
}
