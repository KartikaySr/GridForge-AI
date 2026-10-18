import { afterEach, expect, it, vi } from 'vitest';
import { api, ApiError } from './api';
afterEach(() => vi.unstubAllGlobals());
it('uses same-origin cookies and never an edge bearer credential', async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
  vi.stubGlobal('fetch', fetch);
  await api.login('reader', 'test-password');
  const [path, init] = fetch.mock.calls[0];
  expect(path).toBe('/api/v1/login');
  expect(init.credentials).toBe('same-origin');
  expect(init.headers.Authorization).toBeUndefined();
  expect(init.cache).toBe('no-store');
});
it('turns an expired session into a typed error', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401 }));
  await expect(api.portfolio()).rejects.toBeInstanceOf(ApiError);
});
