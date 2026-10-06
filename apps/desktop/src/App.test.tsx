// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { ErrorBoundary } from './components/ErrorBoundary';
import {
  hasFreshHealth,
  isDesktop,
  runtimeBridge,
  unavailable,
  type RuntimeSnapshot,
} from './lib/runtime';
import { defaults, readPreferences, savePreferences } from './lib/preferences';

vi.mock('./lib/runtime', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./lib/runtime')>();
  return {
    ...actual,
    isDesktop: vi.fn(() => false),
    runtimeBridge: {
      status: vi.fn(),
      intelligence: vi.fn().mockRejectedValue(new Error('unavailable')),
      identity: vi.fn().mockResolvedValue({
        authenticated: true,
        setup_required: false,
        permissions: [],
        user: { username: 'test', role: 'ORG_ADMIN' },
      }),
      restart: vi.fn(),
      stop: vi.fn(),
      diagnostics: vi.fn(),
    },
  };
});

let root: Root;
let container: HTMLDivElement;
const ready = (): RuntimeSnapshot => ({
  ...unavailable,
  state: 'READY',
  generation: 1,
  last_checked_ms: Date.now(),
  message: 'Authenticated shell API ready',
  health: {
    schema_version: '1',
    mode: 'SIMULATION',
    service: 'gridforge-edge',
    status: 'READY',
    readiness_scope: 'shell-only',
    operational_ready: false,
    instance_id: 'test-instance',
    started_at: new Date().toISOString(),
    observed_at: new Date().toISOString(),
    uptime_seconds: 1,
    facility_id: null,
    cloud_state: 'NOT_CONFIGURED',
    sync_state: 'NOT_CONFIGURED',
    components: [],
  },
});
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  localStorage.clear();
  vi.clearAllMocks();
  vi.mocked(isDesktop).mockReturnValue(false);
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});
async function click(text: string) {
  const button = Array.from(container.querySelectorAll('button')).find(
    (element) => element.textContent === text,
  );
  expect(button, `Missing button ${text}`).toBeTruthy();
  await act(async () => button!.click());
}

describe('Phase 1 desktop shell', () => {
  it('renders honest browser preview and reserves future modules without fake data', async () => {
    await act(async () => root.render(<App />));
    expect(container.textContent).toContain('Browser preview.');
    expect(container.textContent).toContain('No facility configured');
    expect(runtimeBridge.status).not.toHaveBeenCalled();
    await click('Telemetry');
    expect(container.textContent).toContain(
      'Open the native desktop to receive live simulator telemetry.',
    );
    expect(container.textContent).not.toContain('₹');
  });
  it('navigates to settings and persists non-sensitive display preferences', async () => {
    await act(async () => root.render(<App />));
    await click('Settings');
    const select = container.querySelector('select')!;
    await act(async () => {
      select.value = 'light';
      select.dispatchEvent(new Event('change', { bubbles: true }));
    });
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(readPreferences().theme).toBe('light');
    expect(container.textContent).toContain('Display preferences saved');
  });
  it('shows native failure and can request a supervised restart', async () => {
    vi.mocked(isDesktop).mockReturnValue(true);
    vi.mocked(runtimeBridge.status)
      .mockResolvedValueOnce({
        ...unavailable,
        state: 'FAILED',
        message: 'Runtime process exited',
      })
      .mockResolvedValue(ready());
    vi.mocked(runtimeBridge.restart).mockResolvedValue();
    await act(async () => root.render(<App />));
    expect(container.textContent).toContain('Runtime process exited');
    await click('System Health');
    await click('Restart runtime');
    expect(runtimeBridge.restart).toHaveBeenCalledTimes(1);
    expect(container.textContent).toContain('Authenticated shell API ready');
  });
  it('disables lifecycle controls in browser preview', async () => {
    await act(async () => root.render(<App />));
    await click('System Health');
    const restart = Array.from(container.querySelectorAll('button')).find(
      (button) => button.textContent === 'Restart runtime',
    )!;
    expect(restart.disabled).toBe(true);
  });
  it('never treats old or future health timestamps as live', () => {
    const snapshot = ready();
    expect(hasFreshHealth(snapshot, snapshot.last_checked_ms! + 1000)).toBe(
      true,
    );
    expect(hasFreshHealth(snapshot, snapshot.last_checked_ms! + 6000)).toBe(
      false,
    );
    expect(hasFreshHealth(snapshot, snapshot.last_checked_ms! - 1)).toBe(false);
    expect(hasFreshHealth({ ...snapshot, state: 'FAILED' })).toBe(false);
  });
  it('recovers safely from corrupt or unavailable preference storage', () => {
    localStorage.setItem('gridforge.desktop.preferences.v1', '{invalid');
    expect(readPreferences()).toEqual(defaults);
    vi.stubGlobal('localStorage', {
      setItem: () => {
        throw new Error('Unavailable');
      },
    });
    expect(savePreferences(defaults)).toBe(false);
    vi.unstubAllGlobals();
  });
  it('shows a recoverable error screen without reflecting exception details', async () => {
    const logging = vi.spyOn(console, 'error').mockImplementation(() => {});
    function Broken(): never {
      throw new Error('sensitive internal detail');
    }
    await act(async () =>
      root.render(
        <ErrorBoundary>
          <Broken />
        </ErrorBoundary>,
      ),
    );
    expect(container.textContent).toContain(
      'The desktop view could not render',
    );
    expect(container.textContent).not.toContain('sensitive internal detail');
    logging.mockRestore();
  });
});
