import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';

afterEach(() => vi.unstubAllGlobals());

describe('scaffold API transport', () => {
  it('returns successful JSON from the configured local API', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ mode: 'SIMULATION' })));
    vi.stubGlobal('fetch', fetchMock);
    expect(await api('/health')).toEqual({ mode: 'SIMULATION' });
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/health');
  });
  it('does not turn an HTTP failure into successful data', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response('{}', { status: 503, statusText: 'Unavailable' }),
        ),
    );
    await expect(api('/health')).rejects.toThrow('503 Unavailable');
  });
  it('propagates connection failure so the caller can mark offline', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new TypeError('Connection failed')),
    );
    await expect(api('/health')).rejects.toThrow('Connection failed');
  });
});
