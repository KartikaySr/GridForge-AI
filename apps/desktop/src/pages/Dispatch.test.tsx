// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';
import type {
  DispatchSnapshot,
  OptimizationSnapshot,
} from '@gridforge/api-client';
import { Dispatch } from './Dispatch';
import { runtimeBridge } from '../lib/runtime';

vi.mock('../lib/runtime', () => ({
  runtimeBridge: {
    dispatch: vi.fn(),
    optimization: vi.fn(),
    dispatchDetail: vi.fn(),
    requestApproval: vi.fn(),
    decideDispatch: vi.fn(),
  },
}));

async function mount(desktop: boolean) {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const container = document.createElement('div');
  document.body.append(container);
  const root = createRoot(container);
  await act(async () => root.render(<Dispatch desktop={desktop} />));
  return {
    container,
    close: async () => {
      await act(async () => root.unmount());
      container.remove();
    },
  };
}
function state(permissions: string[] = ['dispatch.read']): DispatchSnapshot {
  return {
    mode: 'SIMULATION',
    observed_at: new Date().toISOString(),
    timezone: 'UTC',
    actor: 'local-test',
    identity_notice: 'Local simulation session',
    permissions,
    session_expires_at: new Date(Date.now() + 3600000).toISOString(),
    commands: [],
    pending_events: 0,
    command_count: 0,
    capacity: 500,
    worker_error: null,
  };
}
function noProposal(): OptimizationSnapshot {
  return {
    mode: 'SIMULATION',
    observed_at: new Date().toISOString(),
    timezone: 'UTC',
    policies: [],
    latest: null,
    latest_is_current: false,
    pending_events: 0,
    run_count: 0,
    capacity: 500,
  };
}

describe('dispatch screen', () => {
  it('never fabricates a command in browser preview', async () => {
    vi.mocked(runtimeBridge.dispatch).mockClear();
    const view = await mount(false);
    expect(view.container.textContent).toContain('Native desktop required');
    expect(runtimeBridge.dispatch).not.toHaveBeenCalled();
    await view.close();
  });
  it('shows an explicit empty state and disables requests', async () => {
    vi.mocked(runtimeBridge.dispatch).mockResolvedValue(state());
    vi.mocked(runtimeBridge.optimization).mockResolvedValue(noProposal());
    const view = await mount(true);
    expect(view.container.textContent).toContain('No dispatch commands yet');
    expect(view.container.textContent).toContain('No proposal exists');
    const button = [...view.container.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('Request approval'),
    )!;
    expect(button.disabled).toBe(true);
    await view.close();
  });
  it('shows unavailable state without controls', async () => {
    vi.mocked(runtimeBridge.dispatch).mockRejectedValue(new Error('offline'));
    vi.mocked(runtimeBridge.optimization).mockResolvedValue(noProposal());
    const view = await mount(true);
    expect(
      view.container.querySelector('[role="alert"]')?.textContent,
    ).toContain('unavailable');
    expect(
      [...view.container.querySelectorAll('button')].find((b) =>
        b.textContent?.includes('Request approval'),
      )?.disabled,
    ).toBe(true);
    await view.close();
  });
});
