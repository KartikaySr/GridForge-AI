// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';
import { Incidents } from './Incidents';
import { runtimeBridge } from '../lib/runtime';
vi.mock('../lib/runtime', () => ({
  runtimeBridge: {
    incidents: vi.fn(),
    identity: vi.fn(),
    incidentAction: vi.fn(),
  },
}));
async function mount(desktop: boolean) {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const container = document.createElement('div');
  document.body.append(container);
  const root = createRoot(container);
  await act(async () => root.render(<Incidents desktop={desktop} />));
  return {
    container,
    close: async () => {
      await act(async () => root.unmount());
      container.remove();
    },
  };
}
describe('incident controls', () => {
  it('keeps browser preview non-operational', async () => {
    vi.clearAllMocks();
    const view = await mount(false);
    expect(view.container.textContent).toContain('Open the native desktop');
    expect(runtimeBridge.incidents).not.toHaveBeenCalled();
    await view.close();
  });
  it('shows processor failures and gives viewers no mutation controls', async () => {
    vi.mocked(runtimeBridge.identity).mockResolvedValue({
      permissions: ['alert.read'],
    } as Awaited<ReturnType<typeof runtimeBridge.identity>>);
    vi.mocked(runtimeBridge.incidents).mockResolvedValue({
      mode: 'SIMULATION',
      observed_at: '2026-10-06T12:00:00Z',
      incidents: [],
      worker_error: 'INCIDENT_PROCESSING_FAILED',
      processed_sequence: 0,
      pending_events: 2,
      total: 0,
      next_before: null,
    });
    const view = await mount(true);
    expect(view.container.textContent).toContain('INCIDENT_PROCESSING_FAILED');
    expect(view.container.textContent).toContain('2 source events pending');
    expect(view.container.querySelector('textarea')).toBeNull();
    await view.close();
  });
});
