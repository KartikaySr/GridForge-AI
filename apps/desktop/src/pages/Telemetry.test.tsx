// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';
import type { TelemetrySnapshot } from '@gridforge/api-client';
import { Telemetry } from './Telemetry';
import { unavailable } from '../lib/runtime';

vi.mock('../lib/runtime', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/runtime')>()),
  hasFreshHealth: () => true,
}));

const telemetry: TelemetrySnapshot = {
  schema_version: '1',
  mode: 'SIMULATION',
  observed_at: new Date().toISOString(),
  org_id: 'org',
  facility_id: 'facility',
  facility_name: 'Synthetic factory',
  timezone: 'UTC',
  seed: 57,
  tick: 1,
  scenario: 'normal',
  worker_state: 'RUNNING',
  cursor: 5,
  assets: Array.from({ length: 5 }, (_, index) => ({
    asset_id: `SIM-${index + 1}`,
    label: 'Synthetic asset',
    status: 'LIVE',
    point: {
      schema_version: '1',
      org_id: 'org',
      facility_id: 'facility',
      asset_id: `SIM-${index + 1}`,
      device_id: 'factory-simulator-v1',
      line_id: 'simulation-line',
      signal_id: 'active-power',
      metric: 'active_power',
      value: 100,
      unit: 'kW',
      quality: 'GOOD',
      source: 'SIMULATOR',
      event_time: new Date().toISOString(),
      sequence: 1,
      idempotency_key: `key-${index}`,
      received_time: new Date().toISOString(),
      flags: [],
      row_id: index + 1,
      mapping_id: null,
      mapping_revision: null,
    },
  })),
  recent: [],
  accepted: 5,
  duplicates: 0,
  rejected: 0,
  backpressure: 0,
  queue_depth: 0,
  queue_capacity: 8,
  pending_outbox: 5,
  storage_capacity: 250000,
  storage_full: false,
};

describe('Telemetry quality boundaries', () => {
  it('suppresses aggregate load when stale, bad, or disconnected and preserves last known values', async () => {
    Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
    const host = document.createElement('div');
    const root = createRoot(host);
    const snapshot = {
      ...unavailable,
      telemetry,
      telemetry_checked_ms: Date.now(),
    };
    try {
      await act(async () =>
        root.render(<Telemetry desktop snapshot={snapshot} />),
      );
      expect(host.textContent).toContain('500.0 kW');
      for (const status of ['BAD', 'STALE', 'DISCONNECTED'] as const) {
        const data = {
          ...telemetry,
          assets: telemetry.assets.map((asset) => ({ ...asset, status })),
        };
        await act(async () =>
          root.render(
            <Telemetry desktop snapshot={{ ...snapshot, telemetry: data }} />,
          ),
        );
        expect(host.textContent).toContain('Unavailable');
        expect(host.textContent).not.toContain('500.0 kW');
        expect(host.textContent).toContain('Last known sample');
      }
      await act(async () =>
        root.render(
          <Telemetry
            desktop
            snapshot={{ ...snapshot, telemetry_checked_ms: Date.now() - 6000 }}
          />,
        ),
      );
      expect(host.textContent).toContain('Stream disconnected');
      expect(host.querySelector('select')?.disabled).toBe(true);
      expect(host.textContent).not.toContain('500.0 kW');
    } finally {
      await act(async () => root.unmount());
    }
  });
});
