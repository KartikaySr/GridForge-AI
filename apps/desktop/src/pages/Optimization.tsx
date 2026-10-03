import { useEffect, useRef, useState } from 'react';
import type {
  OptimizationSnapshot,
  OptimizationRun,
  PolicyWrite,
  RunRequest,
} from '@gridforge/api-client';
import { runtimeBridge } from '../lib/runtime';

export function Optimization({ desktop }: { desktop: boolean }) {
  const [data, setData] = useState<OptimizationSnapshot | null>(null);
  const [selected, setSelected] = useState<OptimizationRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [clock, setClock] = useState(Date.now());
  const [received, setReceived] = useState(0);
  const [policyId, setPolicyId] = useState('');
  const [duration, setDuration] = useState('300');
  const [message, setMessage] = useState('');
  const pending = useRef<PolicyWrite | RunRequest | null>(null);
  async function refresh() {
    const result = await runtimeBridge.optimization();
    setData(result);
    setReceived(Date.now());
    setClock(Date.now());
    setError(null);
  }
  useEffect(() => {
    if (!desktop) return;
    let active = true;
    let loading = false;
    const poll = async () => {
      setClock(Date.now());
      if (loading) return;
      loading = true;
      try {
        const result = await runtimeBridge.optimization();
        if (active) {
          setData(result);
          setReceived(Date.now());
          setClock(Date.now());
          setError(null);
        }
      } catch {
        if (active)
          setError(
            'Optimization runtime unavailable. Retained results are historical.',
          );
      } finally {
        loading = false;
      }
    };
    void poll();
    const timer = setInterval(() => void poll(), 2000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [desktop]);
  const fresh = !error && clock >= received && clock - received < 5000;
  const run = selected ?? data?.latest;
  const current =
    !selected &&
    fresh &&
    data?.latest_is_current &&
    run?.proposal &&
    clock <= Date.parse(run.proposal.expires_at);
  async function submit(write: PolicyWrite | RunRequest) {
    setBusy(true);
    pending.current = write;
    try {
      if ('policy' in write) {
        const policy = await runtimeBridge.savePolicy(write);
        setPolicyId(policy.id);
        setMessage('Immutable simulation policy saved.');
      } else {
        const result = await runtimeBridge.optimize(write);
        setSelected(null);
        setMessage(`Run recorded: ${result.status}.`);
      }
      pending.current = null;
      await refresh();
    } catch {
      setError(
        'Request failed or response was lost. Retry uses the same request ID to prevent duplicates.',
      );
    } finally {
      setBusy(false);
    }
  }
  if (!desktop)
    return (
      <section className="surface">
        <h2>Native desktop required</h2>
        <p>
          Optimization uses authenticated local services. No preview proposals
          are fabricated.
        </p>
      </section>
    );
  const date = (value: string) =>
    new Date(value).toLocaleString(undefined, {
      timeZone: data?.timezone ?? 'UTC',
    });
  return (
    <div className="optimizationPage">
      <section className="surface">
        <span className="simulationPill">SIMULATION · PROPOSALS ONLY</span>
        <h2>Constraint policy</h2>
        <p>
          Configure flexibility and load bounds in Assets, and a simulation
          demand threshold in Facilities. Each save creates an immutable policy
          version. Allowed window is entered in UTC.
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const form = new FormData(event.currentTarget);
            try {
              const penalties = JSON.parse(
                String(form.get('penalties') || '{}'),
              ) as Record<string, number>;
              void submit({
                request_id: crypto.randomUUID(),
                policy: {
                  name: String(form.get('name')),
                  effective_from: new Date(
                    String(form.get('from')) + 'Z',
                  ).toISOString(),
                  effective_until: new Date(
                    String(form.get('until')) + 'Z',
                  ).toISOString(),
                  max_duration_seconds: Number(form.get('maxDuration')),
                  max_total_reduction_kw: Number(form.get('cap')),
                  asset_penalties: penalties,
                  simulation_rate_per_kwh: String(form.get('rate')) || null,
                  currency: String(form.get('currency')),
                },
              });
            } catch {
              setError(
                'Enter valid UTC dates and a JSON object of asset penalties.',
              );
            }
          }}
        >
          <fieldset disabled={busy || pending.current !== null}>
            <legend>New policy version</legend>
            <label>
              Name
              <input
                name="name"
                required
                maxLength={100}
                placeholder="Simulation curtailment policy"
              />
            </label>
            <label>
              Allowed from (UTC)
              <input name="from" type="datetime-local" required />
            </label>
            <label>
              Allowed until (UTC)
              <input name="until" type="datetime-local" required />
            </label>
            <label>
              Maximum duration (seconds)
              <input
                name="maxDuration"
                type="number"
                min={60}
                max={1800}
                defaultValue={300}
                required
              />
            </label>
            <label>
              Total reduction cap (kW)
              <input
                name="cap"
                type="number"
                min={0.001}
                max={100000000}
                step="any"
                required
              />
            </label>
            <label>
              Simulation rate per kWh (optional)
              <input
                name="rate"
                type="number"
                min={0}
                max={1000000}
                step="0.000001"
              />
            </label>
            <label>
              Currency code
              <input
                name="currency"
                pattern="[A-Z]{3}"
                defaultValue="USD"
                required
              />
            </label>
            <label>
              Relative asset penalties (JSON; lower preferred)
              <input
                name="penalties"
                defaultValue="{}"
                placeholder={'{"SIM-1": 2}'}
              />
            </label>
            <button className="primary" type="submit">
              Save simulation policy
            </button>
          </fieldset>
        </form>
        <p>
          Missing rate leaves economic value incomplete. A rate is a synthetic
          assumption, not a utility tariff.
        </p>
      </section>
      <section className="surface">
        <h2>Evaluate flexibility</h2>
        <label>
          Policy version
          <select
            value={policyId}
            onChange={(e) => setPolicyId(e.target.value)}
          >
            <option value="">Choose a saved policy</option>
            {data?.policies.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {p.id.slice(0, 8)} · {date(p.created_at)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Duration (seconds)
          <input
            type="number"
            min={60}
            max={1800}
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
          />
        </label>
        <button
          className="primary"
          disabled={
            busy ||
            !fresh ||
            !policyId ||
            !!pending.current ||
            Number(duration) < 60 ||
            Number(duration) > 1800
          }
          onClick={() =>
            void submit({
              request_id: crypto.randomUUID(),
              policy_id: policyId,
              duration_seconds: Number(duration),
            })
          }
        >
          Generate simulation proposal
        </button>
        {pending.current && (
          <button
            disabled={busy}
            onClick={() => pending.current && void submit(pending.current)}
          >
            Retry pending request
          </button>
        )}
        {pending.current && (
          <button
            disabled={busy}
            onClick={() => {
              pending.current = null;
              setError(null);
              setMessage(
                'Pending request cleared. Check the latest run before creating another request.',
              );
            }}
          >
            Clear pending request
          </button>
        )}
        {error && <p role="alert">{error}</p>}
        {message && <p role="status">{message}</p>}
        {!data && !error && <p>Loading local optimization state…</p>}
        {data && (
          <p>
            {data.run_count} / {data.capacity} runs stored ·{' '}
            {data.pending_events} audit events pending sync
          </p>
        )}
      </section>
      {run ? (
        <>
          <section className="surface">
            <h2>
              {run.status} ·{' '}
              {current
                ? 'Current proposal evidence'
                : 'Historical result — requires fresh evaluation'}
            </h2>
            <p>{run.explanation}</p>
            <p>
              {date(run.created_at)} ({data?.timezone}) · target{' '}
              {run.required_reduction_kw?.toFixed(2) ?? 'Unknown'} kW · forecast
              peak {run.forecast_peak_kw?.toFixed(2) ?? 'Unknown'} kW ·
              threshold {run.threshold_kw ?? 'Not configured'} kW
            </p>
            <ul>
              {run.constraints.map((c) => (
                <li key={c.code}>
                  {c.passed ? 'PASS' : 'FAIL'} · {c.code}: {c.detail}
                </li>
              ))}
            </ul>
            <h3>Candidate matrix</h3>
            <div className="tableScroll">
              <table>
                <thead>
                  <tr>
                    <th>Asset</th>
                    <th>Current kW</th>
                    <th>Available kW</th>
                    <th>Penalty</th>
                    <th>Selected kW</th>
                    <th>Constraints</th>
                  </tr>
                </thead>
                <tbody>
                  {run.candidates.map((c) => (
                    <tr key={c.asset_id}>
                      <td>
                        {c.name}
                        <br />
                        {c.eligible ? 'ELIGIBLE' : 'REJECTED'}
                      </td>
                      <td>{c.current_kw?.toFixed(2) ?? 'Unknown'}</td>
                      <td>{c.available_kw.toFixed(2)}</td>
                      <td>{c.penalty}</td>
                      <td>{c.selected_kw.toFixed(2)}</td>
                      <td>
                        <details>
                          <summary>
                            {
                              c.constraints.filter(
                                (x) => x.kind === 'HARD' && !x.passed,
                              ).length
                            }{' '}
                            hard failures
                          </summary>
                          <ul>
                            {c.constraints.map((x) => (
                              <li key={x.code}>
                                {x.kind} {x.passed ? 'PASS' : 'FAIL'} · {x.code}
                                : {x.detail}
                              </li>
                            ))}
                          </ul>
                        </details>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {run.proposal && (
              <>
                <h3>Proposal · not authorized</h3>
                <p>{run.proposal.explanation}</p>
                <p>
                  Expected reduction:{' '}
                  {run.proposal.expected_reduction_kw.toFixed(2)} kW for{' '}
                  {run.request.duration_seconds} seconds.
                </p>
                <p>
                  SIMULATED {run.proposal.economic_estimate.status}:{' '}
                  {run.proposal.economic_estimate.amount ?? 'Rate missing'}{' '}
                  {run.proposal.economic_estimate.currency} ·{' '}
                  {run.proposal.economic_estimate.energy_kwh} kWh
                </p>
                <p>{run.proposal.economic_estimate.assumptions}</p>
                <p>
                  Evidence expires {date(run.proposal.expires_at)}. Approval and
                  dispatch are Phase 6 and unavailable here.
                </p>
              </>
            )}
            <details>
              <summary>Input snapshot and traceability</summary>
              <p>
                Run {run.id} · prediction {run.prediction_id ?? 'None'} · policy{' '}
                {run.policy.id} · algorithm {run.algorithm_version}
              </p>
              <pre>
                {JSON.stringify(
                  {
                    policy: run.policy,
                    registry_digest: run.registry_digest,
                    risks: run.risk_ids,
                    registry: run.registry,
                    telemetry: run.telemetry,
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
            <button
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  const previous = await runtimeBridge.optimizationHistory(
                    run.sequence,
                  );
                  if (previous[0]) setSelected(previous[0]);
                  else setMessage('No older runs.');
                } catch {
                  setError('History unavailable.');
                } finally {
                  setBusy(false);
                }
              }}
            >
              Older run
            </button>
            {selected && (
              <button onClick={() => setSelected(null)}>Latest run</button>
            )}
          </section>
        </>
      ) : (
        data && (
          <section className="surface">
            <h2>No optimization runs yet</h2>
            <p>
              Save a policy and evaluate. Insufficient telemetry or flexibility
              produces an explicit infeasible result.
            </p>
          </section>
        )
      )}
    </div>
  );
}
