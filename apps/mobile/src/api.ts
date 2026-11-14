import type {
  MobileSession,
  Portfolio,
  PortalHistory,
  PortalIdentity,
  FieldReportReceipt,
  FieldReportWrite,
} from '@gridforge/api-client';

const configured = process.env.EXPO_PUBLIC_API_ORIGIN ?? '';
export function apiOrigin(value: string): string {
  const url = new URL(value);
  if (
    url.protocol !== 'https:' ||
    url.username ||
    url.password ||
    url.pathname !== '/' ||
    url.search ||
    url.hash
  )
    throw new Error('Configure EXPO_PUBLIC_API_ORIGIN as an HTTPS origin.');
  return url.origin;
}
export class ApiError extends Error {
  constructor(public status: number) {
    super(`Request failed (${status})`);
  }
}
export function client(token?: string) {
  async function request<T>(path: string, body?: unknown): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(
        `${apiOrigin(configured)}/api/v1/mobile${path}`,
        {
          method: body === undefined ? 'GET' : 'POST',
          credentials: 'omit',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: body === undefined ? undefined : JSON.stringify(body),
          signal: controller.signal,
        },
      );
      if (!response.ok) throw new ApiError(response.status);
      return (await response.json()) as T;
    } finally {
      clearTimeout(timeout);
    }
  }
  return {
    login: (username: string, password: string) =>
      request<MobileSession>('/login', { username, password }),
    me: () => request<PortalIdentity>('/me'),
    logout: () => request('/logout', {}),
    portfolio: () => request<Portfolio>('/portfolio'),
    history: (edge: string, stream: string, before?: number) =>
      request<PortalHistory>(
        `/facilities/${encodeURIComponent(edge)}/events?stream=${stream}${before ? `&before=${before}` : ''}`,
      ),
    report: (body: FieldReportWrite) =>
      request<FieldReportReceipt>('/reports', body),
  };
}
export const storageOwner = (userId: string) =>
  `${apiOrigin(configured)}|${userId}`;
