import { useEffect, useState } from 'react';
import type { IntelligenceSnapshot } from '@gridforge/api-client';
import { runtimeBridge } from '../lib/runtime';
import { StatusBadge } from '../components/StatusBadge';

const number = (value: number | null | undefined, suffix = '') =>
  value == null
    ? 'Not available'
    : `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}`;

export function Forecasting({ desktop }: { desktop: boolean }) {
  const [data, setData] = useState<IntelligenceSnapshot | null>(null);
  const [error, setError] = useState(false);
  const [received, setReceived] = useState(0);
  const [clock, setClock] = useState(Date.now);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!desktop) return;
    let active = true;
    let pending = false;
    const refresh = async () => {
      if (pending) return;
      pending = true;
      try {
        const result = await runtimeBridge.intelligence();
        if (active) {
          setData(result);
          const now = Date.now();
          setReceived(now);
          setClock(now);
          setError(false);
        }
      } catch {
        if (active) setError(true);
      } finally {
        pending = false;
      }
    };
    void refresh();
    const timer = setInterval(() => {
      setClock(Date.now());
      void refresh();
    }, 2000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [desktop, retry]);

  if (!desktop)
    return (
      <section className="surface">
        <h2>Forecasting requires the native runtime</h2>
        <p>
          Open the native desktop to collect simulator telemetry. Browser
          preview does not generate forecasts.
        </p>
      </section>
    );
  const connected =
    !error && received > 0 && clock >= received && clock - received <= 5000;
  const prediction = data?.latest;
  const ready =
    connected &&
    data?.status === 'READY' &&
    prediction?.status === 'READY' &&
    Date.parse(prediction.expires_at) >= clock;
  const date = (value: string) =>
    new Intl.DateTimeFormat('en-GB', {
      timeZone: data?.timezone ?? 'UTC',
      dateStyle: 'short',
      timeStyle: 'medium',
    }).format(new Date(value));
  return (
    <>
      <section className="surface forecastPanel">
        <div className="forecastHeading">
          <div>
            <span className="eyebrow">SIMULATION · ADVISORY INTELLIGENCE</span>
            <h2>30-minute facility demand forecast</h2>
          </div>
          <StatusBadge
            state={
              !data
                ? error
                  ? 'OFFLINE'
                  : 'LOADING'
                : !connected
                  ? 'STALE'
                  : ready
                    ? 'READY'
                    : 'DEGRADED'
            }
          />
        </div>
        <p>
          No physical control. Baseline predictions have no calibrated
          confidence or breach probability.
        </p>
        {error && (
          <div role="alert">
            Runtime unavailable. Retained results are historical.{' '}
            <button className="secondary" onClick={() => setRetry(retry + 1)}>
              Retry
            </button>
          </div>
        )}
        {!data && (
          <p role="status">
            {error
              ? 'Could not load intelligence.'
              : 'Loading model, forecast and risk evidence…'}
          </p>
        )}
        {data && (
          <>
            {!ready && (
              <p className="notice" role="status">
                Current forecast unavailable:{' '}
                {data.reason?.replaceAll('_', ' ') ??
                  'Awaiting a fresh runtime result'}
                . Five complete minutes of good telemetry are required (at least
                48 distinct seconds per asset per minute).
              </p>
            )}
            <div className="overviewGrid">
              <div className="metric">
                <span>FORECAST PEAK · MINUTE MEAN</span>
                <strong>
                  {ready
                    ? number(
                        Math.max(...prediction.values.map((p) => p.value_kw)),
                        ' kW',
                      )
                    : 'Unknown'}
                </strong>
                <small>Next 30 minutes</small>
              </div>
              <div className="metric">
                <span>SIMULATION THRESHOLD</span>
                <strong>{number(data.threshold_kw, ' kW')}</strong>
                <small>Configure in Facilities · facility record</small>
              </div>
              <div className="metric">
                <span>CURRENT RISK ASSESSMENT</span>
                <strong>{ready ? data.risk_assessment : 'UNKNOWN'}</strong>
                <small>
                  {data.threshold_kw == null
                    ? 'A threshold has not been configured'
                    : 'Advisory threshold comparison'}
                </small>
              </div>
            </div>
            {prediction && (
              <>
                <DemandChart data={data} showForecast={!!ready} />
                <dl className="keyValues">
                  <dt>Prediction origin ({data.timezone})</dt>
                  <dd>{date(prediction.as_of)}</dd>
                  <dt>Model / feature version</dt>
                  <dd>
                    {prediction.model_version} /{' '}
                    {prediction.evidence.feature_version}
                  </dd>
                  <dt>Prediction ID</dt>
                  <dd className="breakId">{prediction.id}</dd>
                  <dt>Source rows / assets</dt>
                  <dd>
                    {prediction.evidence.row_count} /{' '}
                    {prediction.evidence.asset_ids.length}
                  </dd>
                  <dt>Storage / pending events</dt>
                  <dd>
                    {data.prediction_count} / {data.prediction_capacity}{' '}
                    predictions · {data.pending_events} events
                  </dd>
                </dl>
                <details>
                  <summary>Input provenance and quality coverage</summary>
                  <p>
                    Immutable input window:{' '}
                    {date(prediction.evidence.window_start)} –{' '}
                    {date(prediction.evidence.window_end)} ({data.timezone}). No
                    future samples or later backfills enter the feature window.
                  </p>
                  <p className="breakId">
                    Source SHA-256: {prediction.evidence.source_digest}
                  </p>
                  <p className="breakId">
                    Registry SHA-256: {prediction.evidence.registry_digest}
                  </p>
                  <ul>
                    {prediction.evidence.bins.map((b) => (
                      <li key={b.starts_at}>
                        {date(b.starts_at)} · {number(b.value_kw, ' kW')} ·
                        minimum asset coverage {number(b.coverage * 100, '%')}
                      </li>
                    ))}
                  </ul>
                  <ul>
                    {Object.entries(prediction.evidence.mapping_revisions).map(
                      ([asset, mapping]) => (
                        <li key={asset}>
                          {asset} → {mapping}
                        </li>
                      ),
                    )}
                  </ul>
                </details>
              </>
            )}
          </>
        )}
      </section>
      {data && (
        <div className="twoColumns">
          <section className="surface">
            <span className="eyebrow">MODEL REGISTRY & EVALUATION</span>
            <h2>Measured after the future window closes</h2>
            {data.models.map((m) => (
              <p key={m.version}>
                <strong>
                  {m.version} · {m.status}
                </strong>
                <br />
                {m.algorithm}
                <br />
                {m.training}
              </p>
            ))}
            <p>
              {data.evaluation.method}. Metrics use persisted simulation
              forecasts, not fitted training samples. Overlapping horizons are
              correlated.
            </p>
            <dl className="keyValues">
              <dt>Evaluated / unknown windows</dt>
              <dd>
                {data.evaluation.evaluated_predictions} /{' '}
                {data.evaluation.unknown_predictions}
              </dd>
              <dt>MAE</dt>
              <dd>{number(data.evaluation.mae_kw, ' kW')}</dd>
              <dt>RMSE</dt>
              <dd>{number(data.evaluation.rmse_kw, ' kW')}</dd>
              <dt>MAPE (nonzero actuals only)</dt>
              <dd>{number(data.evaluation.mape_percent, '%')}</dd>
              <dt>Peak precision / recall</dt>
              <dd>
                {number(data.evaluation.peak_precision)} /{' '}
                {number(data.evaluation.peak_recall)}
              </dd>
            </dl>
            {data.evaluation.evaluated_predictions === 0 && (
              <p>
                No evaluated forecast yet. The first result needs five minutes
                of history, then 30 minutes of future telemetry plus a
                five-second receipt allowance.
              </p>
            )}
          </section>
          <section className="surface">
            <span className="eyebrow">RISK LIFECYCLE · LATEST 20</span>
            <h2>Demand threshold evidence</h2>
            <p>
              OPEN → RESOLVED on a fresh forecast below the same threshold.
              Facility configuration changes supersede old risks. Bad data
              leaves an existing risk open with current assessment UNKNOWN.
            </p>
            {!data.risks.length && (
              <p>
                No recorded breach. An empty list is not evidence that demand is
                safe.
              </p>
            )}
            {data.risks.map((risk) => (
              <details className="riskRecord" key={risk.id}>
                <summary>
                  <StatusBadge state={risk.state} />{' '}
                  {number(risk.predicted_peak_kw, ' kW')} /{' '}
                  {number(risk.threshold_kw, ' kW')}
                </summary>
                <p>{risk.reason}</p>
                <p>Severity {risk.severity} · probability uncalibrated</p>
                <p>
                  {date(risk.window_start)} – {date(risk.window_end)} (
                  {data.timezone})
                </p>
                <p>
                  Updated {date(risk.updated_at)} · facility revision{' '}
                  {risk.threshold_revision}
                </p>
                <p className="breakId">
                  Risk: {risk.id}
                  <br />
                  First prediction: {risk.first_prediction_id}
                  <br />
                  Latest prediction: {risk.latest_prediction_id}
                </p>
              </details>
            ))}
          </section>
        </div>
      )}
    </>
  );
}

function DemandChart({
  data,
  showForecast,
}: {
  data: IntelligenceSnapshot;
  showForecast: boolean;
}) {
  const p = data.latest!;
  const actual = p.evidence.bins;
  const maximum =
    Math.max(
      1,
      data.threshold_kw ?? 0,
      ...actual.map((b) => b.value_kw ?? 0),
      ...(showForecast ? p.values.map((v) => v.value_kw) : []),
    ) * 1.1;
  const x = (index: number) => 45 + (index / 34) * 825;
  const y = (value: number) => 185 - (value / maximum) * 150;
  return (
    <figure className="demandChart">
      <svg
        viewBox="0 0 920 235"
        role="img"
        aria-label={
          showForecast
            ? 'Historical minute means and flat 30-minute baseline forecast in kilowatts'
            : 'Historical input minute means; current forecast suppressed'
        }
      >
        <text x="8" y="20">
          kW
        </text>
        <text x="8" y="38">
          {Math.round(maximum)}
        </text>
        <line x1="45" y1="185" x2="870" y2="185" stroke="currentColor" />
        {actual.map((b, i) =>
          b.value_kw == null ? null : (
            <circle
              key={b.starts_at}
              cx={x(i)}
              cy={y(b.value_kw)}
              r="4"
              fill="#56b6ea"
            />
          ),
        )}
        {showForecast && (
          <polyline
            data-testid="forecast-line"
            points={p.values
              .map((v, i) => `${x(i + 5)},${y(v.value_kw)}`)
              .join(' ')}
            fill="none"
            stroke="#65d6ab"
            strokeWidth="3"
            strokeDasharray="7 4"
          />
        )}
        {data.threshold_kw != null && (
          <line
            x1="45"
            x2="870"
            y1={y(data.threshold_kw)}
            y2={y(data.threshold_kw)}
            stroke="#eab86a"
            strokeDasharray="4 4"
          />
        )}
        <text x="45" y="215">
          −5 min history
        </text>
        <text x={x(5)} y="215">
          Origin
        </text>
        <text x="800" y="215">
          +30 min
        </text>
      </svg>
      <figcaption>
        Blue: historical input means · Green dashed: baseline forecast{' '}
        {showForecast ? '' : '(unavailable)'} · Amber: configured simulation
        threshold. kW, minute averages.
      </figcaption>
    </figure>
  );
}
