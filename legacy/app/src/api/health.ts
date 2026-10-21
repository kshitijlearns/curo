import { apiBaseUrl } from './config';

export type HealthCheck = { ok: boolean; detail: string };

export type Health = {
  status: 'ok' | 'error';
  version: string;
  app_env: string;
  mock_mode: boolean;
  providers: Record<string, string>;
  clock: { now: string; source?: string };
  checks: Record<string, HealthCheck>;
};

/** GET /health. A 503 still carries the body, so it is returned rather than thrown. */
export async function fetchHealth(timeoutMs = 6000): Promise<Health> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${apiBaseUrl()}/health`, { signal: controller.signal });
    if (res.status !== 200 && res.status !== 503) {
      throw new Error(`HTTP ${res.status}`);
    }
    return (await res.json()) as Health;
  } finally {
    clearTimeout(timer);
  }
}
