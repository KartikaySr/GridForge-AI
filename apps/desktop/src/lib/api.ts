const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';
export async function api<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
