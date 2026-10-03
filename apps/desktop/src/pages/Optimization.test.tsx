// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';
import { Optimization } from './Optimization';
import { runtimeBridge } from '../lib/runtime';

vi.mock('../lib/runtime', () => ({
  runtimeBridge: {
    optimization: vi.fn(),
    optimize: vi.fn(),
    savePolicy: vi.fn(),
    optimizationHistory: vi.fn(),
  },
}));

async function mount(desktop: boolean) {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const container = document.createElement('div');
  document.body.append(container);
  const root = createRoot(container);
  await act(async () => root.render(<Optimization desktop={desktop} />));
  return {
    container,
    close: async () => {
      await act(async () => root.unmount());
      container.remove();
    },
  };
}

describe('optimization workflow', () => {
  it('does not invent a proposal in browser preview', async () => {
    vi.mocked(runtimeBridge.optimization).mockClear();
    const view = await mount(false);
    expect(view.container.textContent).toContain('Native desktop required');
    expect(runtimeBridge.optimization).not.toHaveBeenCalled();
    await view.close();
  });
  it('shows empty state and prevents running without a policy', async () => {
    vi.mocked(runtimeBridge.optimization).mockResolvedValue({
      mode: 'SIMULATION',
      observed_at: new Date().toISOString(),
      timezone: 'UTC',
      policies: [],
      latest: null,
      latest_is_current: false,
      pending_events: 0,
      run_count: 0,
      capacity: 500,
    });
    const view = await mount(true);
    expect(view.container.textContent).toContain('No optimization runs yet');
    const run = [...view.container.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('Generate simulation'),
    )!;
    expect(run.disabled).toBe(true);
    await view.close();
  });
  it('shows unavailable state without enabling optimization', async () => {
    vi.mocked(runtimeBridge.optimization).mockRejectedValue(
      new Error('offline'),
    );
    const view = await mount(true);
    expect(
      view.container.querySelector('[role="alert"]')?.textContent,
    ).toContain('unavailable');
    expect(
      [...view.container.querySelectorAll('button')].find((b) =>
        b.textContent?.includes('Generate simulation'),
      )?.disabled,
    ).toBe(true);
    await view.close();
  });
  it('retries an uncertain run with exactly the same idempotency key', async () => {
    const now = new Date().toISOString();
    vi.mocked(runtimeBridge.optimization).mockResolvedValue({
      mode: 'SIMULATION',
      observed_at: now,
      timezone: 'UTC',
      policies: [
        {
          id: 'policy',
          version: '1',
          org_id: 'org',
          facility_id: 'facility',
          created_at: now,
          mode: 'SIMULATION',
          name: 'Test',
          effective_from: now,
          effective_until: now,
          max_duration_seconds: 300,
          max_total_reduction_kw: 100,
          currency: 'USD',
          asset_penalties: {},
          simulation_rate_per_kwh: null,
        },
      ],
      latest: null,
      latest_is_current: false,
      pending_events: 1,
      run_count: 0,
      capacity: 500,
    });
    vi.mocked(runtimeBridge.optimize)
      .mockReset()
      .mockRejectedValue(new Error('lost response'));
    const view = await mount(true);
    const select = view.container.querySelector('select')!;
    await act(async () => {
      select.value = 'policy';
      select.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await act(async () =>
      [...view.container.querySelectorAll('button')]
        .find((b) => b.textContent?.includes('Generate simulation'))!
        .click(),
    );
    const first = vi.mocked(runtimeBridge.optimize).mock.calls[0][0];
    await act(async () =>
      [...view.container.querySelectorAll('button')]
        .find((b) => b.textContent?.includes('Retry pending'))!
        .click(),
    );
    expect(vi.mocked(runtimeBridge.optimize).mock.calls[1][0]).toEqual(first);
    await view.close();
  });
});
