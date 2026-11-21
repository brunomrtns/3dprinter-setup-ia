const API_BASE = '/api/fab3d';
export const SSO_LOGIN_BASE = '/id/login';

export function getSsoLoginUrl(redirectPath?: string): string {
  const target = redirectPath || (window.location.pathname + window.location.search) || '/fab3d/';
  return `${SSO_LOGIN_BASE}?redirect=${encodeURIComponent(target.startsWith('/fab3d') ? target : '/fab3d/')}`;
}

export function redirectToSsoLogin(redirectPath?: string): void {
  window.location.href = getSsoLoginUrl(redirectPath);
}

export async function ssoLogout(): Promise<void> {
  localStorage.removeItem('fab3d_token');
  try {
    await fetch('/id/api/auth/logout', { method: 'POST', credentials: 'include' });
  } catch {}
  redirectToSsoLogin('/fab3d/');
}

export function getToken(): string | null {
  return localStorage.getItem('fab3d_token');
}

export function setToken(t: string | null) {
  if (t) localStorage.setItem('fab3d_token', t);
  else localStorage.removeItem('fab3d_token');
}

export async function apiFetch<T = any>(path: string, init: RequestInit = {}, _retried = false): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = { ...(init.headers as Record<string, string> || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!(init.body instanceof FormData) && init.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: 'include',
  });

  // If 401 on first attempt, try silent BI Identity refresh via /id/api/auth/check
  if (res.status === 401 && !_retried) {
    try {
      const chk = await fetch('/id/api/auth/check', { credentials: 'include' });
      if (chk.ok) {
        return apiFetch<T>(path, init, true);
      }
    } catch {}
  }

  if (!res.ok) {
    let msg = `Erro HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data.error) msg = data.error;
    } catch {}
    const err = new Error(msg) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export function downloadUrl(assetId: string, variant: '8k' | '4k' = '4k', key?: string): string {
  const q = new URLSearchParams({ variant });
  const token = getToken();
  if (token) q.set('token', token);
  if (key) q.set('key', key);
  return `${API_BASE}/assets/${assetId}/download?${q.toString()}`;
}
