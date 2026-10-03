// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
import type { DemoSnapshot } from '@gridforge/api-client';
import { Demonstration } from './Demonstration';
import { runtimeBridge } from '../lib/runtime';
vi.mock('../lib/runtime', () => ({
  runtimeBridge: { demo: vi.fn(), demoStep: vi.fn() },
}));
const snapshot: DemoSnapshot = {
  mode: 'SIMULATION',
  clock: 'ACCELERATED_ISOLATED',
  ephemeral: true,
  edge_id: 'edge',
  org_id: 'org',
  facility_id: 'facility',
  simulated_at: '2026-09-30T00:00:00Z',
  next_action: 'approve',
  steps: [],
  telemetry_rows: 3310,
  demand_kw: 6300,
  forecast_status: 'READY',
  risk: 'BREACH',
  run: null,
  command: null,
  verification: null,
  explanation: null,
  audit_integrity_ok: true,
  audit_head: 'hash',
  sync: {
    schema_version: '1',
    mode: 'SIMULATION',
    edge_id: 'edge',
    org_id: 'org',
    facility_id: 'facility',
    observed_at: '2026-09-30T00:00:00Z',
    state: 'NOT_CONFIGURED',
    configured: false,
    pending_count: 3310,
    oldest_pending_at: null,
    oldest_pending_age_seconds: null,
    last_success_at: null,
    conflict_count: 0,
    streams: [],
    conflicts: [],
    message: 'Not configured',
  },
};
it('requires an explicit approval click and keeps the retry request ID', async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.mocked(runtimeBridge.demo).mockResolvedValue(snapshot);
  vi.mocked(runtimeBridge.demoStep)
    .mockRejectedValueOnce(new Error('timeout'))
    .mockResolvedValueOnce({ ...snapshot, next_action: 'verify' });
  const container = document.createElement('div');
  document.body.append(container);
  const root = createRoot(container);
  try {
    await act(async () => root.render(<Demonstration desktop />));
    expect(runtimeBridge.demoStep).not.toHaveBeenCalled();
    expect(container.textContent).toContain('ACCELERATED CLOCK');
    await act(async () => container.querySelector('button')!.click());
    await act(async () => container.querySelector('button')!.click());
    expect(vi.mocked(runtimeBridge.demoStep).mock.calls[0][0]).toEqual(
      vi.mocked(runtimeBridge.demoStep).mock.calls[1][0],
    );
    expect(container.textContent).toContain('Measure rebound');
  } finally {
    await act(async () => root.unmount());
    container.remove();
  }
});
it('does not claim cloud completion when no receiver is configured', async () => {
  vi.mocked(runtimeBridge.demo).mockResolvedValue({
    ...snapshot,
    next_action: 'disconnect',
  });
  const container = document.createElement('div');
  const root = createRoot(container);
  try {
    await act(async () => root.render(<Demonstration desktop />));
    expect(container.querySelector('button')!.disabled).toBe(true);
    expect(container.textContent).toContain('no cloud success is claimed');
  } finally {
    await act(async () => root.unmount());
  }
});
