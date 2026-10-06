import { useEffect, useState } from 'react';
import type {
  IntelligenceSnapshot,
  TelemetrySnapshot,
} from '@gridforge/api-client';
import { runtimeBridge } from '../lib/runtime';

export function DemandOverview({
  desktop,
  telemetry,
  fresh,
}: {
  desktop: boolean;
  telemetry: TelemetrySnapshot | null | undefined;
  fresh: boolean;
}) {
  const [data, setData] = useState<IntelligenceSnapshot | null>(null);
  const [failed, setFailed] = useState(false);
  const [clock, setClock] = useState(Date.now);
  useEffect(() => {
    if (!desktop) return;
    let active = true,
      pending = false;
    const refresh = async () => {
      if (pending) return;
      pending = true;
      try {
        const next = await runtimeBridge.intelligence();
        if (active) {
          setData(next);
          setFailed(false);
        }
      } catch {
        if (active) setFailed(true);
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
  }, [desktop]);
  const age = telemetry ? clock - Date.parse(telemetry.observed_at) : Infinity;
  const live =
    fresh &&
    age >= -1000 &&
    age <= 5000 &&
    !!telemetry?.assets.length &&
    telemetry.assets.every(
      (a) =>
        a.status === 'LIVE' &&
        a.point &&
        a.point.quality === 'GOOD' &&
        !a.point.flags.length &&
        clock - Date.parse(a.point.event_time) >= -1000 &&
        clock - Date.parse(a.point.event_time) <= 5000,
    );
  const load = live
    ? telemetry!.assets.reduce((sum, a) => sum + (a.point?.value ?? 0), 0)
    : null;
  const observedAge = data ? clock - Date.parse(data.observed_at) : Infinity;
  const ready =
    !failed &&
    observedAge >= -1000 &&
    observedAge <= 5000 &&
    data?.status === 'READY' &&
    data.latest?.status === 'READY' &&
    Date.parse(data.latest.expires_at) >= clock;
  const prediction = ready ? data!.latest : null;
  const threshold = ready ? data!.threshold_kw : null;
  const peak = prediction?.values.length
    ? Math.max(...prediction.values.map((v) => v.value_kw))
    : null;
  const display = (v: number | null | undefined) =>
    v == null ? 'Unavailable' : `${v.toFixed(1)} kW`;
  const bins =
    prediction?.evidence.bins.filter((b) => b.value_kw != null) ?? [];
  const values = prediction?.values ?? [];
  const max = Math.max(
    1,
    threshold ?? 0,
    ...bins.map((b) => b.value_kw ?? 0),
    ...values.map((v) => v.value_kw),
  );
  const count = bins.length + values.length;
  const x = (i: number) => 50 + (i * 690) / Math.max(1, count - 1);
  const y = (v: number) => 180 - (v / max) * 150;
  return (
    <section className="surface">
      <h2>Facility demand · SIMULATION</h2>
      <div className="overviewGrid">
        <div className="metric">
          <span>CURRENT LOAD</span>
          <strong>{display(load)}</strong>
          <small>
            {live
              ? 'Good, fresh simulator readings'
              : 'Telemetry incomplete, stale or unavailable'}
          </small>
        </div>
        <div className="metric">
          <span>FORECAST PEAK · 30 MIN</span>
          <strong>{display(peak)}</strong>
          <small>{prediction?.model_version ?? 'No valid forecast'}</small>
        </div>
        <div className="metric">
          <span>THRESHOLD / HEADROOM</span>
          <strong>{display(threshold)}</strong>
          <small>
            {threshold != null && load != null
              ? `${display(threshold - load)} headroom`
              : 'Headroom unavailable'}
          </small>
        </div>
        <div className="metric">
          <span>RISK</span>
          <strong>{ready ? data!.risk_assessment : 'UNKNOWN'}</strong>
          <small>
            {failed
              ? 'Intelligence connection unavailable'
              : (data?.reason ?? 'Models advise; approval remains separate')}
          </small>
        </div>
      </div>
      {prediction && count > 1 ? (
        <>
          <svg
            viewBox="0 0 780 220"
            width="100%"
            role="img"
            aria-label="Demand chart: recent measured minute means, rolling-mean forecast and threshold in kilowatts"
          >
            <text x="4" y="18" fill="currentColor">
              {max.toFixed(0)} kW
            </text>
            <text x="20" y="184" fill="currentColor">
              0
            </text>
            <line x1="50" y1="180" x2="740" y2="180" stroke="currentColor" />
            {threshold != null && (
              <line
                x1="50"
                y1={y(threshold)}
                x2="740"
                y2={y(threshold)}
                stroke="var(--warn)"
                strokeDasharray="6 4"
              />
            )}
            <polyline
              fill="none"
              stroke="var(--good)"
              strokeWidth="3"
              points={bins
                .map((b, i) => `${x(i)},${y(b.value_kw ?? 0)}`)
                .join(' ')}
            />
            <polyline
              fill="none"
              stroke="var(--accent)"
              strokeWidth="3"
              strokeDasharray="8 3"
              points={values
                .map((v, i) => `${x(i + bins.length)},${y(v.value_kw)}`)
                .join(' ')}
            />
            <text x="50" y="207" fill="currentColor">
              −5 min actual
            </text>
            <text x="300" y="207" fill="currentColor">
              Forecast → +30 min
            </text>
          </svg>
          <p>
            Green: measured minute means · Blue dashed: forecast · Amber dashed:
            threshold. Forecast as of {prediction.as_of}. This statistical
            baseline cannot anticipate an unseen spike.
          </p>
        </>
      ) : (
        <p>
          No chart until complete, fresh forecasting evidence is available.
          Inspect Telemetry and Forecasting & Risk for the cause.
        </p>
      )}
    </section>
  );
}
