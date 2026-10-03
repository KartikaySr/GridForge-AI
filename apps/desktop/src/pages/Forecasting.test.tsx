// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';
import type { IntelligenceSnapshot } from '@gridforge/api-client';
import { Forecasting } from './Forecasting';
import { runtimeBridge } from '../lib/runtime';

vi.mock('../lib/runtime', () => ({ runtimeBridge: { intelligence: vi.fn() } }));

function fixture(): IntelligenceSnapshot {
  const now = new Date().toISOString();
  return {
    schema_version: '1',
    mode: 'SIMULATION',
    observed_at: now,
    org_id: 'org',
    facility_id: 'facility',
    timezone: 'UTC',
    status: 'READY',
    reason: null,
    worker_error: null,
    risk_assessment: 'BREACH',
    threshold_kw: 450,
    pending_events: 2,
    prediction_count: 1,
    prediction_capacity: 1440,
    models: [],
    risks: [],
    evaluation: {
      method: 'Chronological evaluation',
      evaluated_predictions: 0,
      unknown_predictions: 0,
      mae_kw: null,
      rmse_kw: null,
      mape_percent: null,
      peak_precision: null,
      peak_recall: null,
    },
    latest: {
      sequence: 1,
      id: 'prediction-id',
      org_id: 'org',
      facility_id: 'facility',
      mode: 'SIMULATION',
      as_of: now,
      created_at: now,
      expires_at: new Date(Date.now() + 65000).toISOString(),
      model_version: 'rolling-mean-v1',
      status: 'READY',
      reason: null,
      unit: 'kW',
      target: 'Minute means',
      horizon_minutes: 30,
      confidence: null,
      threshold_kw: 450,
      threshold_revision: 2,
      evidence: {
        feature_version: 'minute-coverage-v1',
        window_start: now,
        window_end: now,
        asset_ids: ['asset-1'],
        mapping_revisions: { 'asset-1': 'mapping:1' },
        registry_digest: 'registry-sha',
        source_digest: 'source-sha',
        row_count: 300,
        first_row: 1,
        last_row: 300,
        reason: null,
        bins: [{ starts_at: now, ends_at: now, value_kw: 500, coverage: 1 }],
      },
      values: Array.from({ length: 30 }, () => ({
        starts_at: now,
        ends_at: now,
        value_kw: 500,
      })),
    },
  };
}

describe('Forecast and risk visibility', () => {
  it('shows baseline provenance and unavailable evaluation without invented accuracy', async () => {
    Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
    vi.mocked(runtimeBridge.intelligence).mockResolvedValue(fixture());
    const host = document.createElement('div');
    const root = createRoot(host);
    try {
      await act(async () => root.render(<Forecasting desktop />));
      expect(host.textContent).toContain('rolling-mean-v1');
      expect(host.textContent).toContain('source-sha');
      expect(host.textContent).toContain('No evaluated forecast yet');
      expect(host.textContent).toContain('BREACH');
      expect(
        host.querySelector('[data-testid="forecast-line"]'),
      ).not.toBeNull();
    } finally {
      await act(async () => root.unmount());
    }
  });
  it('suppresses retained numbers and current breach after disconnect', async () => {
    Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
    vi.useFakeTimers();
    vi.mocked(runtimeBridge.intelligence)
      .mockResolvedValueOnce(fixture())
      .mockRejectedValue(new Error('offline'));
    const host = document.createElement('div');
    const root = createRoot(host);
    try {
      await act(async () => root.render(<Forecasting desktop />));
      expect(
        host.querySelector('[data-testid="forecast-line"]'),
      ).not.toBeNull();
      await act(async () => vi.advanceTimersByTimeAsync(6000));
      expect(host.querySelector('[data-testid="forecast-line"]')).toBeNull();
      expect(host.textContent).toContain('UNKNOWN');
      expect(host.textContent).toContain('Retained results are historical');
      expect(host.textContent).not.toContain('BREACH');
    } finally {
      await act(async () => root.unmount());
      vi.useRealTimers();
    }
  });
  it('does not invoke native APIs or fabricate predictions in browser preview', async () => {
    Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
    vi.clearAllMocks();
    const host = document.createElement('div');
    const root = createRoot(host);
    try {
      await act(async () => root.render(<Forecasting desktop={false} />));
      expect(runtimeBridge.intelligence).not.toHaveBeenCalled();
      expect(host.textContent).toContain(
        'Browser preview does not generate forecasts',
      );
    } finally {
      await act(async () => root.unmount());
    }
  });
  it('renders degraded input without a forecast curve', async () => {
    Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
    const data = fixture();
    data.status = 'DEGRADED';
    data.reason = 'BAD_TELEMETRY_QUALITY';
    data.risk_assessment = 'UNKNOWN';
    vi.mocked(runtimeBridge.intelligence).mockResolvedValue(data);
    const host = document.createElement('div');
    const root = createRoot(host);
    try {
      await act(async () => root.render(<Forecasting desktop />));
      expect(host.textContent).toContain('BAD TELEMETRY QUALITY');
      expect(host.querySelector('[data-testid="forecast-line"]')).toBeNull();
    } finally {
      await act(async () => root.unmount());
    }
  });
});
