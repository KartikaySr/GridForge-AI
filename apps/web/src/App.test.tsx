// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
import { App } from './App';
import { api } from './api';
vi.mock('./api', () => ({
  ApiError: class extends Error {
    status = 401;
  },
  api: {
    me: vi.fn(),
    portfolio: vi.fn(),
    history: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  },
}));
it('offers sign-in without exposing edge credentials or a registration flow', async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.mocked(api.me).mockRejectedValue(new Error('signed out'));
  const host = document.createElement('div'),
    root = createRoot(host);
  await act(async () => root.render(<App />));
  expect(host.querySelector('input[type="password"]')).not.toBeNull();
  expect(host.textContent).toContain(
    'Desktop credentials are managed separately',
  );
  expect(api.history).not.toHaveBeenCalled();
  await act(async () => root.unmount());
});
it('shows an explicit empty authorized portfolio without invented facility data', async () => {
  vi.mocked(api.me).mockResolvedValue({
    id: 'user',
    username: 'reader',
    permission: 'portfolio.read',
    expires_at: new Date(Date.now() + 3600000).toISOString(),
  });
  vi.mocked(api.portfolio).mockResolvedValue({
    mode: 'SIMULATION',
    observed_at: new Date().toISOString(),
    facilities: [],
    limit: 100,
  });
  const host = document.createElement('div'),
    root = createRoot(host);
  await act(async () => root.render(<App />));
  expect(host.textContent).toContain('No facilities assigned');
  expect(host.textContent).toContain('READ ONLY');
  await act(async () => root.unmount());
});
it('clears protected views when the session has expired', async () => {
  vi.mocked(api.me).mockResolvedValue({
    id: 'user',
    username: 'reader',
    permission: 'portfolio.read',
    expires_at: new Date(Date.now() - 1000).toISOString(),
  });
  const host = document.createElement('div'),
    root = createRoot(host);
  await act(async () => root.render(<App />));
  expect(host.querySelector('input[type="password"]')).not.toBeNull();
  expect(host.textContent).toContain('Your session ended');
  await act(async () => root.unmount());
});
it('removes old evidence when the facility selection is cleared', async () => {
  vi.mocked(api.me).mockResolvedValue({
    id: 'user',
    username: 'reader',
    permission: 'portfolio.read',
    expires_at: new Date(Date.now() + 3600000).toISOString(),
  });
  vi.mocked(api.portfolio).mockResolvedValue({
    mode: 'SIMULATION',
    observed_at: new Date().toISOString(),
    limit: 100,
    facilities: [
      {
        edge_id: 'edge',
        org_id: 'org',
        facility_id: 'facility',
        enabled: true,
        last_received_at: null,
        freshness: 'NO_DATA',
      },
    ],
  });
  vi.mocked(api.history).mockResolvedValue({
    mode: 'SIMULATION',
    observed_at: new Date().toISOString(),
    edge_id: 'edge',
    stream: 'telemetry',
    next_before: null,
    events: [
      {
        event_id: 'event',
        sequence: 1,
        stream: 'telemetry',
        event_type: 'VisibleTelemetry',
        received_at: new Date().toISOString(),
        body: {},
      },
    ],
  });
  const host = document.createElement('div'),
    root = createRoot(host);
  await act(async () => root.render(<App />));
  expect(host.textContent).toContain('VisibleTelemetry');
  await act(async () => {
    const select = host.querySelector('select')!;
    select.value = '';
    select.dispatchEvent(new Event('change', { bubbles: true }));
  });
  expect(host.textContent).not.toContain('VisibleTelemetry');
  await act(async () => root.unmount());
});
