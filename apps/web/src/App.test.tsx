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
