import { useEffect, useRef, useState } from 'react';
import type { DemoSnapshot, DemoStep } from '@gridforge/api-client';
import { runtimeBridge } from '../lib/runtime';

const labels: Record<DemoStep['action'], string> = {
  normal: 'Generate normal factory telemetry',
  bad: 'Inject bad-quality telemetry',
  peak: 'Restore quality and simulate demand peak',
  propose: 'Evaluate constraints and request approval',
  approve: 'Approve isolated simulated dispatch',
  verify: 'Measure rebound and verify simulated savings',
  explain: 'Explain the decision with cited evidence',
  disconnect: 'Disconnect demo cloud and continue locally',
  reconnect: 'Reconnect and reconcile pending events',
};
export function Demonstration({ desktop }: { desktop: boolean }) {
  const [snapshot, setSnapshot] = useState<DemoSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const pending = useRef<DemoStep | null>(null);
  useEffect(() => {
    if (!desktop) return;
    let active = true;
    void runtimeBridge
      .demo()
      .then((value) => {
        if (active) setSnapshot(value);
      })
      .catch(() => {
        if (active)
          setError(
            'An administrator session is required to open the isolated demonstration.',
          );
      });
    return () => {
      active = false;
    };
  }, [desktop]);
  const cloudRequired =
    snapshot?.next_action === 'disconnect' ||
    snapshot?.next_action === 'reconnect';
  async function advance() {
    if (!snapshot?.next_action) return;
    setBusy(true);
    setError('');
    pending.current ??= {
      request_id: crypto.randomUUID(),
      action: snapshot.next_action,
    };
    try {
      setSnapshot(await runtimeBridge.demoStep(pending.current));
      pending.current = null;
    } catch {
      setError(
        'Step did not finish. Retry uses the same request ID. Check demo cloud enrollment if this is a synchronization step.',
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="demoPage">
      <section className="surface">
        <span className="eyebrow">ISOLATED SIMULATION · ACCELERATED CLOCK</span>
        <h2>Follow a complete energy decision</h2>
        <p>
          This rehearsal generates one sample per simulated second in a separate
          temporary facility. It leaves your operational facility unchanged.
          Each click advances the simulation; it does not measure real elapsed
          time or control physical equipment.
        </p>
        <p>
          Rehearsal records last until the runtime restarts. Copy the evidence
          before closing. Forecasting uses the current rolling-mean baseline;
          savings are synthetic.
        </p>
        {!desktop && <p>Open the native desktop to run the demonstration.</p>}
        {snapshot && (
          <>
            <div className="demoMetrics">
              <div>
                <small>Simulated time</small>
                <strong>
                  {new Date(snapshot.simulated_at).toLocaleString()}
                </strong>
              </div>
              <div>
                <small>Telemetry rows</small>
                <strong>{snapshot.telemetry_rows.toLocaleString()}</strong>
              </div>
              <div>
                <small>Demand</small>
                <strong>{snapshot.demand_kw.toFixed(1)} kW</strong>
              </div>
              <div>
                <small>Risk</small>
                <strong>{snapshot.risk}</strong>
              </div>
            </div>
            {snapshot.next_action ? (
              <button
                disabled={busy || (cloudRequired && !snapshot.sync.configured)}
                onClick={() => {
                  void advance();
                }}
              >
                {busy
                  ? 'Running bounded simulation…'
                  : labels[snapshot.next_action]}
              </button>
            ) : (
              <p role="status">
                Complete scenario verified, including cloud reconciliation.
              </p>
            )}
            {snapshot.next_action === 'approve' && (
              <p>
                Your click explicitly authorizes the displayed proposal for this
                isolated simulator only.
              </p>
            )}
            {cloudRequired && !snapshot.sync.configured && (
              <p role="status">
                Local demonstration complete. Cloud rehearsal requires a
                separately enrolled demo receiver; no cloud success is claimed
                while disconnected or unconfigured.
              </p>
            )}
            <button
              className="secondary"
              disabled={busy}
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(
                    JSON.stringify(snapshot, null, 2),
                  );
                  setNotice('Demonstration evidence copied.');
                } catch {
                  setError('Clipboard access failed.');
                }
              }}
            >
              Copy evidence
            </button>
            <p role="status">{notice}</p>
          </>
        )}
        {error && <p role="alert">{error}</p>}
      </section>
      {snapshot && (
        <>
          <section className="surface">
            <h2>Evidence trail</h2>
            <ol>
              {snapshot.steps.map((step) => (
                <li key={step.action}>
                  <strong>{labels[step.action]}</strong>
                  <p>{step.detail}</p>
                </li>
              ))}
            </ol>
          </section>
          {snapshot.run && (
            <section className="surface">
              <h2>Constraint decision</h2>
              <p>{snapshot.run.explanation}</p>
              <p>
                Forecast {snapshot.run.forecast_peak_kw?.toFixed(1)} kW ·
                Threshold {snapshot.run.threshold_kw} kW · Proposed reduction{' '}
                {snapshot.run.proposal?.expected_reduction_kw.toFixed(1)} kW
              </p>
              <ul>
                {snapshot.run.candidates.map((candidate) => (
                  <li key={candidate.asset_id}>
                    {candidate.asset_id}:{' '}
                    {candidate.eligible ? 'Eligible' : 'Excluded'} · Selected{' '}
                    {candidate.selected_kw.toFixed(1)} kW
                  </li>
                ))}
              </ul>
              <details>
                <summary>Inspect complete constraint evidence</summary>
                <pre>{JSON.stringify(snapshot.run, null, 2)}</pre>
              </details>
            </section>
          )}
          {snapshot.command && (
            <section className="surface">
              <h2>Dispatch and measured verification</h2>
              <p>Command state: {snapshot.command.state}</p>
              <p>
                Approved by:{' '}
                {snapshot.command.approved_by ?? 'Awaiting human approval'}
              </p>
              <p>
                Verification:{' '}
                {snapshot.verification?.status ?? 'Not yet measured'}
              </p>
              {snapshot.verification && (
                <p>
                  Net simulated energy value:{' '}
                  {snapshot.verification.net_energy_value ?? 'Incomplete'} USD.
                  Demand-charge savings are not verified.
                </p>
              )}
            </section>
          )}
          {snapshot.explanation && (
            <section className="surface">
              <h2>Advisory explanation</h2>
              <p>{snapshot.explanation.answer}</p>
              <small>
                Provider: {snapshot.explanation.provider}. Cited local evidence;
                no control authority.
              </small>
            </section>
          )}
          <section className="surface">
            <h2>Continuity and audit</h2>
            <p>
              Cloud: {snapshot.sync.state} · Pending events:{' '}
              {snapshot.sync.pending_count} · Audit chain:{' '}
              {snapshot.audit_integrity_ok ? 'Verified' : 'FAILED'}
            </p>
            <details>
              <summary>Demo enrollment identity</summary>
              <p>Edge: {snapshot.edge_id}</p>
              <p>Organization: {snapshot.org_id}</p>
              <p>Facility: {snapshot.facility_id}</p>
            </details>
          </section>
        </>
      )}
    </div>
  );
}
