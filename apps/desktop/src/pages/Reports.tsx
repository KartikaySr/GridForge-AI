import { useEffect, useRef, useState } from 'react';
import type {
  ProductionReport,
  ProductionWrite,
  ReportComparison,
} from '@gridforge/api-client';
import { runtimeBridge } from '../lib/runtime';

export function Reports({ desktop }: { desktop: boolean }) {
  const [reports, setReports] = useState<ProductionReport[]>([]);
  const [before, setBefore] = useState<number | null>(null);
  const [canCreate, setCanCreate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [baseline, setBaseline] = useState('');
  const [comparison, setComparison] = useState('');
  const [result, setResult] = useState<ReportComparison | null>(null);
  const pending = useRef<{ body: string; requestId: string } | null>(null);
  useEffect(() => {
    if (!desktop) return;
    let active = true;
    void Promise.all([runtimeBridge.identity(), runtimeBridge.reports()])
      .then(([identity, data]) => {
        if (active) {
          setCanCreate(identity.permissions.includes('report.create'));
          setReports(data.reports);
          setBefore(data.next_before);
        }
      })
      .catch(() => {
        if (active)
          setNotice('Reports are unavailable. Check sign-in and permissions.');
      });
    return () => {
      active = false;
    };
  }, [desktop]);
  if (!desktop)
    return (
      <section className="surface">
        <h2>Production & Reports</h2>
        <p>Open the native desktop to inspect local evidence.</p>
      </section>
    );
  return (
    <div className="reportingPage">
      <section className="surface">
        <h2>Production-normalized electricity</h2>
        <p>
          SIMULATION · Local-only reports · Output and rejects are operator
          declarations. Reports do not establish industrial savings or
          independent quality verification.
        </p>
        <p>
          Use closed UTC intervals of 1–3,600 seconds. Every asset needs one
          good measurement per second. Reports are immutable; correct a
          declaration by creating a new report.
        </p>
        <p role="status">{notice}</p>
        {canCreate && (
          <form
            onSubmit={async (event) => {
              event.preventDefault();
              const data = new FormData(event.currentTarget);
              const values = {
                product: String(data.get('product')),
                starts_at: String(data.get('starts_at')),
                ends_at: String(data.get('ends_at')),
                asset_ids: String(data.get('assets'))
                  .split(',')
                  .map((s) => s.trim())
                  .filter(Boolean),
                good_tonnes: String(data.get('good')),
                rejected_tonnes: String(data.get('rejects')),
                note: String(data.get('note')),
              };
              const body = JSON.stringify(values);
              if (pending.current?.body !== body)
                pending.current = { body, requestId: crypto.randomUUID() };
              const write: ProductionWrite = {
                ...values,
                request_id: pending.current.requestId,
              };
              setBusy(true);
              setNotice('');
              try {
                const report = await runtimeBridge.createReport(write);
                setReports((old) => [
                  report,
                  ...old.filter((r) => r.id !== report.id),
                ]);
                pending.current = null;
                setNotice(
                  report.status === 'COMPLETE'
                    ? 'Complete simulation report saved.'
                    : `Incomplete report saved: ${report.reason}`,
                );
              } catch {
                setNotice(
                  'Report rejected or unavailable. Check UTC dates, registered assets, permissions and closed interval. Retry unchanged inputs safely.',
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            <div className="reportFields">
              <label>
                Product / SKU
                <input name="product" required maxLength={100} />
              </label>
              <label>
                Start UTC (ISO 8601)
                <input
                  name="starts_at"
                  required
                  placeholder="2026-10-06T10:00:00Z"
                />
              </label>
              <label>
                End UTC (ISO 8601)
                <input
                  name="ends_at"
                  required
                  placeholder="2026-10-06T10:01:00Z"
                />
              </label>
              <label>
                Registered asset IDs (comma-separated)
                <input name="assets" required placeholder="SIM-1,SIM-2" />
              </label>
              <label>
                Good output (tonnes)
                <input
                  name="good"
                  type="number"
                  min="0.000001"
                  max="1000000"
                  step="0.000001"
                  required
                />
              </label>
              <label>
                Rejected output (tonnes)
                <input
                  name="rejects"
                  type="number"
                  min="0"
                  max="1000000"
                  step="0.000001"
                  required
                />
              </label>
              <label>
                Declaration and operating context
                <textarea name="note" required maxLength={500} />
              </label>
            </div>
            <button disabled={busy}>Create simulation report</button>
          </form>
        )}
      </section>
      <section className="surface">
        <h2>Report history</h2>
        {!reports.length && <p>No reports loaded.</p>}
        {reports.map((report) => (
          <article className="reportEntry" key={report.id}>
            <h3>
              {report.declaration.product} · {report.status}
            </h3>
            <p>
              {report.declaration.starts_at} to {report.declaration.ends_at}
            </p>
            <p>
              Assets: {report.declaration.asset_ids.join(', ')} · Evidence:{' '}
              {report.valid_seconds}/{report.expected_seconds} seconds
            </p>
            <p>
              Electricity: {report.energy_kwh ?? 'Unavailable'} kWh · SEC:{' '}
              {report.sec_kwh_per_good_tonne ?? 'Unavailable'} kWh / good tonne
            </p>
            <p>
              Declared output: {report.declaration.good_tonnes} good tonnes,{' '}
              {report.declaration.rejected_tonnes} rejected tonnes
            </p>
            {report.reason && <p>{report.reason}</p>}
            <button
              disabled={busy}
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(
                    JSON.stringify(report, null, 2),
                  );
                  setNotice('Simulation report copied as JSON.');
                } catch {
                  setNotice('Clipboard unavailable.');
                }
              }}
            >
              Copy JSON report
            </button>
          </article>
        ))}
        {before !== null && (
          <button
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                const data = await runtimeBridge.reports(before);
                setReports((old) => [
                  ...old,
                  ...data.reports.filter(
                    (r) => !old.some((o) => o.id === r.id),
                  ),
                ]);
                setBefore(data.next_before);
              } catch {
                setNotice('Older reports are unavailable.');
              } finally {
                setBusy(false);
              }
            }}
          >
            Load older reports
          </button>
        )}
      </section>
      <section className="surface">
        <h2>Comparable-period review</h2>
        <p>
          Same product, assets, mapping revisions and duration. Baseline must
          precede comparison. Lower declared throughput or higher rejects blocks
          an improvement claim. Negative SEC change means lower energy per good
          tonne.
        </p>
        <label>
          Baseline report
          <select
            value={baseline}
            onChange={(e) => {
              setBaseline(e.target.value);
              setResult(null);
            }}
          >
            <option value="">Select baseline</option>
            {reports.map((r) => (
              <option key={r.id} value={r.id}>
                {r.declaration.product} · {r.declaration.starts_at}
              </option>
            ))}
          </select>
        </label>
        <label>
          Comparison report
          <select
            value={comparison}
            onChange={(e) => {
              setComparison(e.target.value);
              setResult(null);
            }}
          >
            <option value="">Select comparison</option>
            {reports.map((r) => (
              <option key={r.id} value={r.id}>
                {r.declaration.product} · {r.declaration.starts_at}
              </option>
            ))}
          </select>
        </label>
        <button
          disabled={busy || !baseline || !comparison || baseline === comparison}
          onClick={async () => {
            setBusy(true);
            setResult(null);
            try {
              setResult(
                await runtimeBridge.compareReports({
                  baseline_id: baseline,
                  comparison_id: comparison,
                }),
              );
            } catch {
              setNotice('Comparison is unavailable.');
            } finally {
              setBusy(false);
            }
          }}
        >
          Compare reports
        </button>
        {result && (
          <div role="status">
            <h3>{result.status}</h3>
            <p>
              {result.sec_change_percent === null
                ? 'No supported improvement claim.'
                : `SEC change: ${result.sec_change_percent}%`}
            </p>
            <p>{result.reasons.join('; ')}</p>
            <p>{result.interpretation}</p>
          </div>
        )}
      </section>
    </div>
  );
}
