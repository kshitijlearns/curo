/**
 * The typed client. Every call goes to CURO's own API under /api/v1 — the browser never talks
 * to a vendor and never holds a secret. Types come only from the generated OpenAPI schema
 * (`npm run gen:api`), so the web app and the API can't drift.
 */
import type { components } from '@/api/schema';
import { DEMO, DemoError, demoApi, demoChat, demoPersonaChat } from './demo';
import { getToken, signOut } from './session';

export type S = components['schemas'];

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(typeof detail === 'string' ? detail : messageOf(detail) || `Request failed (${status})`);
  }
}

/** A 402 from the API: out of credits, or a limit reached. The shell shows the upgrade screen. */
export type Limit = {
  code: 'out_of_credits' | 'revision_limit' | 'agent_chat_limit';
  resource?: string;
  plan?: string;
  message: string;
};

function messageOf(detail: unknown): string {
  if (detail && typeof detail === 'object' && 'message' in detail) {
    return String((detail as { message: unknown }).message);
  }
  if (Array.isArray(detail)) return 'Check what you entered and try again.';
  return '';
}

export const BASE = '/api/v1';

export async function api<T>(
  path: string,
  init: { method?: string; body?: unknown; signal?: AbortSignal } = {},
): Promise<T> {
  if (DEMO) {
    try {
      return (await demoApi(init.method ?? (init.body === undefined ? 'GET' : 'POST'), path, init.body)) as T;
    } catch (e) {
      if (e instanceof DemoError) {
        if (e.status === 402 && e.detail && typeof e.detail === 'object') {
          window.dispatchEvent(new CustomEvent<Limit>('curo:limit', { detail: e.detail as Limit }));
        }
        throw new ApiError(e.status, e.detail);
      }
      throw e;
    }
  }
  const token = await getToken();
  const res = await fetch(`${BASE}${path}`, {
    method: init.method ?? (init.body === undefined ? 'GET' : 'POST'),
    headers: {
      ...(init.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
    signal: init.signal,
  });
  if (res.status === 401 && token) {
    await signOut();
    if (typeof window !== 'undefined') window.location.assign('/login');
  }
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      detail = (await res.json()).detail;
    } catch {
      /* not JSON */
    }
    if (res.status === 402 && detail && typeof detail === 'object') {
      window.dispatchEvent(new CustomEvent<Limit>('curo:limit', { detail: detail as Limit }));
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Wait for a background job (studio steps, simulations) to finish. */
export async function waitForJob(jobId: string, onProgress?: (p: Record<string, unknown>) => void) {
  for (let i = 0; i < 600; i++) {
    const job = await api<S['JobOut']>(`/jobs/${jobId}`);
    onProgress?.((job.progress ?? {}) as Record<string, unknown>);
    if (job.status === 'succeeded') return job;
    if (job.status === 'failed') throw new ApiError(409, job.error || 'That didn’t work. Try again.');
    await new Promise((r) => setTimeout(r, i < 10 ? 400 : 1200));
  }
  throw new ApiError(504, 'This is taking longer than usual. Check back in a minute.');
}

/** Ask Curo: a streamed reply (server-sent events over a POST). */
export async function* chatStream(body: S['ChatIn']): AsyncGenerator<{ event: string; data: any }> {
  if (DEMO) {
    yield* demoChat();
    return;
  }
  yield* sse('/chat', body);
}

/** Chat with a Follower Persona (v2.2): the same event stream (delta, done, error). */
export async function* personaChatStream(
  personaId: string,
  body: S['PersonaChatIn'],
): AsyncGenerator<{ event: string; data: any }> {
  if (DEMO) {
    yield* demoPersonaChat(personaId, body.message);
    return;
  }
  yield* sse(`/personas/${personaId}/chat`, body);
}

async function* sse(path: string, body: unknown): AsyncGenerator<{ event: string; data: any }> {
  const token = await getToken();
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) throw new ApiError(res.status, 'Curo couldn’t answer just now.');
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let cut;
    while ((cut = buf.indexOf('\n\n')) >= 0) {
      const block = buf.slice(0, cut);
      buf = buf.slice(cut + 2);
      let event = 'message';
      let data = '';
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim();
        else if (line.startsWith('data:')) data += line.slice(5).trim();
      }
      let parsed: any = data;
      try {
        parsed = JSON.parse(data);
      } catch {
        /* plain text */
      }
      if (event === 'error' && parsed?.code === 'out_of_credits') {
        window.dispatchEvent(new CustomEvent<Limit>('curo:limit', { detail: parsed }));
      }
      yield { event, data: parsed };
    }
  }
}

/** Upload a recorded video: a signed URL from the API, then the file straight to storage. */
export async function uploadVideo(file: File): Promise<string> {
  const type = file.type === 'video/quicktime' ? 'video/quicktime' : 'video/mp4';
  const signed = await api<S['UploadSigned']>('/uploads/sign', { body: { content_type: type } });
  if (DEMO) return signed.path; // the demo has nowhere to store a video
  // Local storage signs a URL on this API (/v1/…); Supabase signs its own.
  const url = signed.url.startsWith('/v1/') ? `/api${signed.url}` : signed.url;
  const put = await fetch(url, {
    method: signed.method || 'PUT',
    headers: (signed.headers as Record<string, string>) ?? { 'Content-Type': type },
    body: file,
  });
  if (!put.ok) throw new ApiError(put.status, 'The upload didn’t go through. Try again.');
  return signed.path;
}

/** A text response (the recap's share card SVG). */
export async function apiText(path: string): Promise<string> {
  if (DEMO) return String(await demoApi('GET', path, undefined));
  const token = await getToken();
  const res = await fetch(`${BASE}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new ApiError(res.status, 'Couldn’t load that.');
  return res.text();
}
