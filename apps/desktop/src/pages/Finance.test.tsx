// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';
import type { DispatchSnapshot, FinanceSnapshot } from '@gridforge/api-client';
import { Finance } from './Finance';
import { runtimeBridge } from '../lib/runtime';

vi.mock('../lib/runtime', () => ({
  runtimeBridge: {
    finance: vi.fn(),
    dispatch: vi.fn(),
    saveTariff: vi.fn(),
    verifySavings: vi.fn(),
  },
}));

async function mount(
  desktop: boolean,
  page: 'Energy & Tariffs' | 'Verification & Savings',
) {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const container = document.createElement('div');
  document.body.append(container);
  const root = createRoot(container);
  await act(async () => root.render(<Finance desktop={desktop} page={page} />));
  return {
    container,
    close: async () => {
      await act(async () => root.unmount());
      container.remove();
    },
  };
}
const finance = (): FinanceSnapshot => ({
  mode: 'SIMULATION',
  observed_at: new Date().toISOString(),
  timezone: 'UTC',
  tariffs: [],
  verifications: [],
  ledger: [],
  pending_events: 0,
  tariff_count: 0,
  verification_count: 0,
  worker_error: null,
});
const dispatch = (): DispatchSnapshot => ({
  mode: 'SIMULATION',
  observed_at: new Date().toISOString(),
  timezone: 'UTC',
  actor: 'test',
  identity_notice: 'Local simulation session',
  permissions: [],
  session_expires_at: new Date(Date.now() + 3600000).toISOString(),
  commands: [],
  pending_events: 0,
  command_count: 0,
  capacity: 500,
  worker_error: null,
});

describe('simulation finance screens', () => {
  it('does not contact finance in browser preview', async () => {
    vi.mocked(runtimeBridge.finance).mockClear();
    const view = await mount(false, 'Energy & Tariffs');
    expect(view.container.textContent).toContain('Native desktop required');
    expect(runtimeBridge.finance).not.toHaveBeenCalled();
    await view.close();
  });
  it('shows empty financial state and blocks verification without a completed command', async () => {
    vi.mocked(runtimeBridge.finance).mockResolvedValue(finance());
    vi.mocked(runtimeBridge.dispatch).mockResolvedValue(dispatch());
    const view = await mount(true, 'Verification & Savings');
    expect(view.container.textContent).toContain('No ledger entries');
    expect(view.container.textContent).toContain(
      'Demand charges remain unassessed',
    );
    const button = [...view.container.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('Start verification'),
    )!;
    expect(button.disabled).toBe(true);
    await view.close();
  });
});
