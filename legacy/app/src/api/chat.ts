/**
 * Ask Curo over the API (MVP doc §7: POST /v1/chat; logic doc §14).
 *
 * The reply streams as server-sent events. React Native's fetch can't read a response as it
 * arrives, so this uses XMLHttpRequest, whose responseText grows as the events come in (on
 * the phone and on the web). Events (api/curo/routes/chat.py):
 *   meta  {message_id, intent, handoff}  handoff "studio": apply it as the Studio step's change
 *   tool  {name, status}                 a tool running on the creator's records
 *   job   {job_id, step}                 a change running as a job
 *   delta {text}                         the next checked sentence
 *   reset {}                             clear what was shown; a corrected reply follows
 *   done  {message_id, text, sources, checked, jobs}
 *   error {message}
 */
import { api, unwrap, type Schemas } from './client';
import { apiBaseUrl } from './config';
import { useSession } from '@/state/session';

export type ChatSource = Schemas['ChatSource'];
export type ChatMessage = Schemas['ChatMessageOut'];
export type Memory = Schemas['MemoryOut'];
export type ChatScreen = Schemas['ChatIn']['screen'];
export type ChatBody = {
  message: string;
  screen: ChatScreen;
  project_id?: string | null;
  simulation_id?: string | null;
  frame_id?: string | null;
};
export type ChatMeta = { message_id: string; intent: string; handoff: 'studio' | null };
export type ChatJob = { job_id: string; step: 'script' | 'storyboard' | null };
export type ChatDone = {
  message_id: string;
  text: string;
  sources: ChatSource[];
  checked: 'model' | 'model_retry' | 'template';
  jobs: ChatJob[];
};
export type ChatHandlers = {
  meta?: (m: ChatMeta) => void;
  tool?: (name: string, status: 'running' | 'done' | 'failed') => void;
  job?: (job: ChatJob) => void;
  delta?: (text: string) => void;
  reset?: () => void;
};

type SseEvent = { event: string; data: unknown };

/** Complete events in the buffer, and what's left over (an event still arriving). */
export function parseSSE(buffer: string): { events: SseEvent[]; rest: string } {
  const blocks = buffer.replace(/\r\n/g, '\n').split('\n\n');
  const rest = blocks.pop() ?? '';
  const events: SseEvent[] = [];
  for (const block of blocks) {
    let event = 'message';
    const data: string[] = [];
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
    }
    if (!data.length) continue;
    try {
      events.push({ event, data: JSON.parse(data.join('\n')) });
    } catch {
      // a malformed event is skipped, not fatal
    }
  }
  return { events, rest };
}

/** Send a message and follow the streamed reply. Resolves with the finished reply, or null
 * when the message was handed to the Studio step (the caller applies it there). */
export function sendChat(body: ChatBody, on: ChatHandlers = {}): Promise<ChatDone | null> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    let seen = 0;
    let buffer = '';
    let done: ChatDone | null = null;
    let handoff = false;
    let failed: string | null = null;

    const handle = ({ event, data }: SseEvent) => {
      const d = data as Record<string, unknown>;
      if (event === 'meta') {
        handoff = d.handoff === 'studio';
        on.meta?.(d as unknown as ChatMeta);
      } else if (event === 'tool') on.tool?.(String(d.name), d.status as 'running');
      else if (event === 'job') on.job?.(d as unknown as ChatJob);
      else if (event === 'delta') on.delta?.(String(d.text ?? ''));
      else if (event === 'reset') on.reset?.();
      else if (event === 'done') done = d as unknown as ChatDone;
      else if (event === 'error') failed = String(d.message ?? 'Curo couldn’t answer just now.');
    };
    const pump = () => {
      const text = xhr.responseText ?? '';
      if (text.length <= seen) return;
      buffer += text.slice(seen);
      seen = text.length;
      const parsed = parseSSE(buffer);
      buffer = parsed.rest;
      parsed.events.forEach(handle);
    };

    xhr.open('POST', `${apiBaseUrl()}/v1/chat`);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.setRequestHeader('Accept', 'text/event-stream');
    const token = useSession.getState().session?.token;
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.onprogress = pump;
    xhr.onreadystatechange = () => {
      if (xhr.readyState === 3) pump();
      if (xhr.readyState !== 4) return;
      pump();
      if (buffer.trim()) parseSSE(`${buffer}\n\n`).events.forEach(handle);
      if (xhr.status === 401 && useSession.getState().session) useSession.getState().signOut();
      if (xhr.status !== 200) {
        let detail = `Request failed (${xhr.status})`;
        try {
          const parsed = JSON.parse(xhr.responseText) as { detail?: unknown };
          if (typeof parsed.detail === 'string') detail = parsed.detail;
        } catch {
          // not JSON
        }
        reject(new Error(detail));
      } else if (failed) reject(new Error(failed));
      else if (handoff) resolve(null);
      else if (done) resolve(done);
      else reject(new Error('Curo’s reply was cut off. Try again.'));
    };
    xhr.onerror = () => reject(new Error('Curo couldn’t be reached. Check your connection.'));
    xhr.send(JSON.stringify(body));
  });
}

/** The conversation so far about one simulation (project memory). */
export async function chatHistory(simulationId: string): Promise<ChatMessage[]> {
  return unwrap(await api.GET('/v1/chat', { params: { query: { simulation_id: simulationId } } }));
}

export async function listMemory(): Promise<Memory[]> {
  return unwrap(await api.GET('/v1/memory'));
}

export async function deleteMemory(id: string): Promise<void> {
  const res = await api.DELETE('/v1/memory/{memory_id}', {
    params: { path: { memory_id: id } },
  });
  if (!res.response.ok) unwrap(res);
}

/** What the reply is doing while a tool runs. */
export const TOOL_ACTIVITY: Record<string, string> = {
  search_reels: 'Looking through your reels…',
  get_reel: 'Reading that reel…',
  get_pattern_cards: 'Checking your patterns…',
  get_opportunity: 'Reading the opportunity…',
  score_idea: 'Scoring the idea…',
  get_draft: 'Reading your draft…',
  rewrite_script: 'Changing the script…',
  update_frame: 'Redrawing the frame…',
  get_simulation: 'Reading the simulation…',
  run_simulation: 'Re-scoring the what-if…',
  compare_to_draft: 'Comparing with your draft…',
  remember: 'Saving that…',
  forget: 'Forgetting that…',
};

const SOURCE_KIND: Record<ChatSource['kind'], string> = {
  reel: 'Your reel',
  pattern: 'Pattern',
  opportunity: 'Opportunity',
  idea: 'Idea',
  project: 'Draft',
  simulation: 'Simulation',
  memory: 'Memory',
};

export function sourceLabel(s: ChatSource): string {
  return `${SOURCE_KIND[s.kind]} · ${s.title}`;
}
