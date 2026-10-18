import type {
  PortalHistory,
  PortalIdentity,
  Portfolio,
} from '@gridforge/api-client';
export class ApiError extends Error {
  constructor(public status: number) {
    super(`Request failed (${status})`);
  }
}
async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    credentials: 'same-origin',
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(10000),
    cache: 'no-store',
  });
  if (!response.ok) throw new ApiError(response.status);
  return response.json() as Promise<T>;
}
export const api = {
  me: () => request<PortalIdentity>('/me'),
  login: (username: string, password: string) =>
    request<PortalIdentity>('/login', { username, password }),
  logout: () => request<{ signed_out: boolean }>('/logout', {}),
  portfolio: () => request<Portfolio>('/portfolio'),
  history: (edge: string, stream: string, before: number | null = null) =>
    request<PortalHistory>(
      `/facilities/${encodeURIComponent(edge)}/events?stream=${encodeURIComponent(stream)}${before ? `&before=${before}` : ''}`,
    ),
};
