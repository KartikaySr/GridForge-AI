import { useEffect, useRef, useState } from 'react';
import type {
  DispatchSnapshot,
  FinanceSnapshot,
  TariffWrite,
  VerificationRequest,
} from '@gridforge/api-client';
import { runtimeBridge } from '../lib/runtime';

export function Finance({
  desktop,
  page,
}: {
  desktop: boolean;
  page: 'Energy & Tariffs' | 'Verification & Savings';
}) {
  const [finance, setFinance] = useState<FinanceSnapshot | null>(null);
  const [dispatch, setDispatch] = useState<DispatchSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState('Simulation flat energy rate');
  const [currency, setCurrency] = useState('USD');
  const [rate, setRate] = useState('0.15');
  const [demandRate, setDemandRate] = useState('');
  const [commandId, setCommandId] = useState('');
  const [tariffId, setTariffId] = useState('');
  const pending = useRef<TariffWrite | VerificationRequest | null>(null);

  async function refresh() {
    const [f, d] = await Promise.all([
      runtimeBridge.finance(),
      runtimeBridge.dispatch(),
    ]);
    setFinance(f);
    setDispatch(d);
    setCommandId(
      (old) =>
        old ||
        d.commands.find((command) => command.state === 'COMPLETED')?.id ||
        '',
    );
    setTariffId((old) => old || f.tariffs[0]?.id || '');
    setError(null);
  }
  useEffect(() => {
    if (!desktop) return;
    let active = true;
    const poll = async () => {
      try {
        const [f, d] = await Promise.all([
          runtimeBridge.finance(),
          runtimeBridge.dispatch(),
        ]);
        if (active) {
          setFinance(f);
          setDispatch(d);
          setCommandId(
            (old) =>
              old ||
              d.commands.find((command) => command.state === 'COMPLETED')?.id ||
              '',
          );
          setTariffId((old) => old || f.tariffs[0]?.id || '');
          setError(null);
        }
      } catch (cause) {
        if (active) setError(`Finance runtime unavailable: ${String(cause)}`);
      }
    };
    void poll();
    const timer = setInterval(() => void poll(), 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [desktop]);

  async function submit(write: TariffWrite | VerificationRequest) {
    pending.current = write;
    setBusy(true);
    try {
      if ('tariff' in write) await runtimeBridge.saveTariff(write);
      else await runtimeBridge.verifySavings(write);
      pending.current = null;
      setNotice('Saved to the local simulated finance record.');
      await refresh();
    } catch {
      setError(
        'Request rejected or response lost. Refresh the record, then retry the same request ID.',
      );
    } finally {
      setBusy(false);
    }
  }
  if (!desktop)
    return (
      <section className="surface">
        <h2>Native desktop required</h2>
        <p>Simulation finance uses the authenticated local runtime.</p>
      </section>
    );
  const format = (value: string) =>
    new Date(value).toLocaleString(undefined, {
      timeZone: finance?.timezone || 'UTC',
    });
  const canVerify =
    dispatch?.commands.filter(
      (command) =>
        command.state === 'COMPLETED' &&
        !finance?.verifications.some((v) => v.command_id === command.id),
    ) || [];
  return (
    <div className="financePage">
      <section className="surface">
        <span className="simulationPill">
          SIMULATION ONLY · USER-ENTERED TARIFF
        </span>
        <h2>{page}</h2>
        <p>
          Currency and rates are assumptions for the simulator, not utility
          prices. A pre-dispatch forecast supplies the declared baseline.
          Verified values require complete execution and rebound telemetry.
          Demand charges remain unassessed without billing-period evidence.
        </p>
        <p>
          {finance
            ? `${finance.tariff_count} tariff versions · ${finance.verification_count} verification cases · ${finance.pending_events} audit events pending sync`
            : 'Loading finance state…'}
        </p>
        {finance?.worker_error && (
          <p role="alert">Finance worker: {finance.worker_error}</p>
        )}
        {error && <p role="alert">{error}</p>}
        {notice && <p role="status">{notice}</p>}
        {pending.current && (
          <button
            disabled={busy}
            onClick={() => pending.current && void submit(pending.current)}
          >
            Retry same request ID
          </button>
        )}
        <button className="secondary" onClick={() => void refresh()}>
          Refresh
        </button>
      </section>
      {page === 'Energy & Tariffs' ? (
        <>
          <section className="surface">
            <h2>Create immutable simulation tariff version</h2>
            <p>
              One flat energy band covers the previous and next 30 days. The
              billing period is recorded but demand-charge savings are not
              calculated.
            </p>
            <label>
              Name{' '}
              <input value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label>
              Currency code{' '}
              <input
                value={currency}
                maxLength={3}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
              />
            </label>
            <label>
              Energy rate per kWh{' '}
              <input
                type="number"
                min="0"
                step="0.000001"
                value={rate}
                onChange={(e) => setRate(e.target.value)}
              />
            </label>
            <label>
              Demand rate per kW, optional{' '}
              <input
                type="number"
                min="0"
                step="0.000001"
                value={demandRate}
                onChange={(e) => setDemandRate(e.target.value)}
              />
            </label>
            <button
              disabled={
                busy ||
                !name.trim() ||
                !/^[A-Z]{3}$/.test(currency) ||
                !rate.trim() ||
                !Number.isFinite(Number(rate)) ||
                Number(rate) < 0 ||
                (demandRate !== '' &&
                  (!Number.isFinite(Number(demandRate)) ||
                    Number(demandRate) < 0))
              }
              onClick={() => {
                const now = Date.now();
                const start = new Date(now - 30 * 24 * 3600_000);
                const end = new Date(now + 30 * 24 * 3600_000);
                void submit({
                  request_id: crypto.randomUUID(),
                  tariff: {
                    name,
                    currency,
                    effective_from: start.toISOString(),
                    effective_until: end.toISOString(),
                    billing_period_start: start.toISOString(),
                    billing_period_end: end.toISOString(),
                    energy_bands: [
                      {
                        starts_at: start.toISOString(),
                        ends_at: end.toISOString(),
                        rate_per_kwh: rate,
                      },
                    ],
                    demand_charge_rate_per_kw: demandRate || null,
                  },
                });
              }}
            >
              Save tariff version
            </button>
          </section>
          <section className="surface">
            <h2>Saved versions</h2>
            {finance?.tariffs.length ? (
              finance.tariffs.map((tariff) => (
                <article key={tariff.id}>
                  <strong>{tariff.name}</strong> · {tariff.currency} ·{' '}
                  {tariff.energy_bands[0]?.rate_per_kwh}/kWh
                  <p>
                    Effective {format(tariff.effective_from)} to{' '}
                    {format(tariff.effective_until)} · Demand rate{' '}
                    {tariff.demand_charge_rate_per_kw ?? 'none'} ·{' '}
                    {tariff.source}
                  </p>
                  <small>{tariff.id}</small>
                </article>
              ))
            ) : (
              <p>No simulation tariff has been entered.</p>
            )}
          </section>
        </>
      ) : (
        <>
          <section className="surface">
            <h2>Verify a completed simulated command</h2>
            <p>
              The execution and equal-length rebound windows must contain one
              good mapped sample per asset for every second. Verification may
              remain pending until the rebound window ends.
            </p>
            <label>
              Completed command{' '}
              <select
                value={commandId}
                onChange={(e) => setCommandId(e.target.value)}
              >
                <option value="">Choose command</option>
                {canVerify.map((command) => (
                  <option key={command.id} value={command.id}>
                    {command.id} · {command.state}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Tariff version{' '}
              <select
                value={tariffId}
                onChange={(e) => setTariffId(e.target.value)}
              >
                <option value="">Choose tariff</option>
                {finance?.tariffs.map((tariff) => (
                  <option key={tariff.id} value={tariff.id}>
                    {tariff.name} · {tariff.id}
                  </option>
                ))}
              </select>
            </label>
            <button
              disabled={busy || !commandId || !tariffId}
              onClick={() =>
                void submit({
                  request_id: crypto.randomUUID(),
                  command_id: commandId,
                  tariff_id: tariffId,
                })
              }
            >
              Start verification
            </button>
          </section>
          <section className="surface">
            <h2>Verification cases</h2>
            {finance?.verifications.length ? (
              finance.verifications.map((v) => (
                <article key={v.id}>
                  <strong>{v.status}</strong> · command {v.command_id}
                  <p>{v.reason}</p>
                  <p>
                    Baseline {v.baseline_kw} kW · measured reduction{' '}
                    {v.measured_reduction_kw ?? '—'} kW · rebound{' '}
                    {v.rebound_kwh ?? '—'} kWh
                  </p>
                  <p>
                    Gross avoided {v.gross_avoided_cost ?? '—'} · rebound cost{' '}
                    {v.rebound_cost ?? '—'} · net energy value{' '}
                    {v.net_energy_value ?? '—'} {v.tariff.currency}
                  </p>
                  <p>
                    Execution {v.execution?.valid_slots ?? 0}/
                    {v.execution?.expected_slots ?? '—'} seconds · rebound{' '}
                    {v.rebound?.valid_slots ?? 0}/
                    {v.rebound?.expected_slots ?? '—'} seconds · demand charge{' '}
                    {v.demand_charge.status}
                  </p>
                  <small>
                    Forecast {v.prediction_id} · proposal {v.proposal_id} ·
                    tariff {v.tariff.id}
                  </small>
                </article>
              ))
            ) : (
              <p>No verification cases yet.</p>
            )}
          </section>
          <section className="surface">
            <h2>Separate estimate and verified ledger</h2>
            {finance?.ledger.length ? (
              finance.ledger.map((entry) => (
                <article key={entry.id}>
                  <strong>{entry.status}</strong> · {entry.amount}{' '}
                  {entry.currency}
                  <p>{entry.note}</p>
                  <small>
                    #{entry.sequence} · {entry.method} · {entry.input_digest}
                  </small>
                </article>
              ))
            ) : (
              <p>No ledger entries.</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
