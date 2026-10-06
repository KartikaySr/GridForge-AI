// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Reports } from './Reports';
import { runtimeBridge } from '../lib/runtime';

vi.mock('../lib/runtime', () => ({
  runtimeBridge: {
    identity: vi.fn(),
    reports: vi.fn(),
    createReport: vi.fn(),
    compareReports: vi.fn(),
  },
}));
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(runtimeBridge.identity).mockResolvedValue({
    permissions: ['report.read'],
  } as Awaited<ReturnType<typeof runtimeBridge.identity>>);
  vi.mocked(runtimeBridge.reports).mockResolvedValue({
    mode: 'SIMULATION',
    reports: [],
    sequences: [],
    next_before: null,
  });
});
async function mount(desktop: boolean) {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const container = document.createElement('div');
  document.body.append(container);
  const root = createRoot(container);
  await act(async () => root.render(<Reports desktop={desktop} />));
  return {
    container,
    close: async () => {
      await act(async () => root.unmount());
      container.remove();
    },
  };
}
describe('Production reporting', () => {
  it('keeps browser preview non-operational', async () => {
    const view = await mount(false);
    expect(view.container.textContent).toContain('Open the native desktop');
    expect(runtimeBridge.reports).not.toHaveBeenCalled();
    await view.close();
  });
  it('withholds creation from a read-only identity', async () => {
    const view = await mount(true);
    expect(runtimeBridge.reports).toHaveBeenCalled();
    expect(view.container.querySelector('form')).toBeNull();
    await view.close();
  });
  it('retains a request UUID after an uncertain creation failure', async () => {
    vi.mocked(runtimeBridge.identity).mockResolvedValue({
      permissions: ['report.read', 'report.create'],
    } as Awaited<ReturnType<typeof runtimeBridge.identity>>);
    vi.mocked(runtimeBridge.createReport).mockRejectedValue(
      new Error('offline'),
    );
    const view = await mount(true);
    for (const [name, value] of Object.entries({
      product: 'casting',
      starts_at: '2026-10-01T10:00:00Z',
      ends_at: '2026-10-01T10:01:00Z',
      assets: 'SIM-1',
      good: '1',
      rejects: '0',
      note: 'fixture',
    })) {
      const input = view.container.querySelector(
        `[name="${name}"]`,
      ) as HTMLInputElement;
      input.value = value;
    }
    const form = view.container.querySelector('form')!;
    await act(async () => {
      form.dispatchEvent(
        new Event('submit', { bubbles: true, cancelable: true }),
      );
    });
    expect(view.container.textContent).toContain(
      'Report rejected or unavailable',
    );
    await act(async () => {
      form.dispatchEvent(
        new Event('submit', { bubbles: true, cancelable: true }),
      );
    });
    expect(runtimeBridge.createReport).toHaveBeenCalledTimes(2);
    expect(
      vi.mocked(runtimeBridge.createReport).mock.calls[0][0].request_id,
    ).toBe(vi.mocked(runtimeBridge.createReport).mock.calls[1][0].request_id);
    await view.close();
  });
});
