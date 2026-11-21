const API_BASE = '/api/fab3d';

export function getToken(): string | null {
  return localStorage.getItem('fab3d_token');
}

export function setToken(t: string | null) {
  if (t) localStorage.setItem('fab3d_token', t);
  else localStorage.removeItem('fab3d_token');
}

export async function apiFetch<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = { ...(init.headers as Record<string, string> || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!(init.body instanceof FormData) && init.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    let msg = `Erro HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data.error) msg = data.error;
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}

export function downloadUrl(assetId: string, variant: '8k' | '4k' = '4k', key?: string): string {
  const token = getToken() || '';
  const q = new URLSearchParams({ variant, token });
  if (key) q.set('key', key);
  return `${API_BASE}/assets/${assetId}/download?${q.toString()}`;
}
