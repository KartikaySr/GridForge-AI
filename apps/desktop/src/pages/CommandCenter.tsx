import {
  ArrowRight,
  CheckCircle2,
  CircleDashed,
  Server,
  ShieldCheck,
} from 'lucide-react';
import { hasFreshHealth, type RuntimeSnapshot } from '../lib/runtime';
import { StatusBadge } from '../components/StatusBadge';

export function CommandCenter({
  snapshot,
  openHealth,
}: {
  snapshot: RuntimeSnapshot;
  openHealth: () => void;
}) {
  const fresh = hasFreshHealth(snapshot);
  return (
    <>
      <section className="overviewGrid" aria-label="Platform readiness">
        <div className="metric">
          <Server size={18} />
          <span>LOCAL RUNTIME</span>
          <strong>
            {fresh
              ? 'Ready'
              : snapshot.state === 'READY'
                ? 'Stale'
                : snapshot.state.toLowerCase()}
          </strong>
          <small>
            {fresh
              ? 'Authenticated shell API'
              : 'No current health confirmation'}
          </small>
        </div>
        <div className="metric">
          <ShieldCheck size={18} />
          <span>CONTROL MODE</span>
          <strong>Simulation</strong>
          <small>Physical writes unavailable</small>
        </div>
        <div className="metric">
          <CircleDashed size={18} />
          <span>FACILITY CONTEXT</span>
          <strong>
            {snapshot.telemetry
              ? snapshot.telemetry.facility_name
              : 'Not configured'}
          </strong>
          <small>Facility registry available</small>
        </div>
        <div className="metric">
          <CircleDashed size={18} />
          <span>TELEMETRY</span>
          <strong>
            {fresh && snapshot.telemetry
              ? 'Simulation active'
              : 'Not connected'}
          </strong>
          <small>Inspect the Telemetry module for quality</small>
        </div>
      </section>
      <div className="workspaceColumns">
        <section className="surface">
          <div className="sectionHeader">
            <div>
              <span className="eyebrow">LOCAL EXECUTION</span>
              <h2>Desktop readiness</h2>
            </div>
            <StatusBadge
              state={
                fresh
                  ? 'READY'
                  : snapshot.state === 'READY'
                    ? 'STALE'
                    : snapshot.state
              }
            />
          </div>
          <ol className="startupList">
            <li>
              <CheckCircle2 />
              <div>
                <strong>Application shell</strong>
                <p>Navigation, display preferences and diagnostics.</p>
              </div>
              <span>Available</span>
            </li>
            <li>
              {fresh ? <CheckCircle2 /> : <CircleDashed />}
              <div>
                <strong>Authenticated local runtime</strong>
                <p>{snapshot.message}</p>
              </div>
              <span>{fresh ? 'Ready' : 'Waiting'}</span>
            </li>
            <li>
              <CircleDashed />
              <div>
                <strong>Durable edge state</strong>
                <p>SQLite WAL, migrations and transactional outbox.</p>
              </div>
              <span>{fresh ? 'Available' : 'Waiting'}</span>
            </li>
            <li>
              <CircleDashed />
              <div>
                <strong>Live facility telemetry</strong>
                <p>
                  Authenticated simulator stream; quality and freshness remain
                  explicit.
                </p>
              </div>
              <span>{fresh ? 'Available' : 'Waiting'}</span>
            </li>
          </ol>
          <button className="secondary" onClick={openHealth}>
            Inspect system health <ArrowRight size={16} />
          </button>
        </section>
        <section className="surface">
          <span className="eyebrow">OPERATIONAL BOUNDARY</span>
          <h2>Local shell is the first step</h2>
          <p className="muted">
            API readiness confirms communication with the runtime. It does not
            establish readiness for optimization, dispatch or financial
            verification.
          </p>
          <dl className="keyValues">
            <dt>Cloud connection</dt>
            <dd>Not configured</dd>
            <dt>Synchronization</dt>
            <dd>Not implemented</dd>
            <dt>User identity</dt>
            <dd>Local session only</dd>
            <dt>Operational authority</dt>
            <dd>Not provisioned</dd>
          </dl>
        </section>
      </div>
      <section className="surface">
        <span className="eyebrow">
          PLATFORM DECISION CHAIN · TARGET ARCHITECTURE
        </span>
        <div className="decisionChain">
          {[
            'Telemetry',
            'Validation',
            'State',
            'Forecast',
            'Risk',
            'Constraints',
            'Optimization',
            'Proposal',
            'Authorization',
            'Dispatch',
            'Acknowledgement',
            'Verification',
            'Savings',
            'Audit',
          ].map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>
        <p className="muted">
          Baseline forecasting and risk are available in Forecasting & Risk.
          Models advise; constraints and authorization remain authoritative.
        </p>
      </section>
    </>
  );
}
