/**
 * Demo mode (D211): the web app deployed without a backend plays back the demo creator's
 * journey, recorded from the real API by tools/record_web_demo.py (public/demo/fixtures.json).
 * Every screen shows real CURO output for the synthetic @curo.demo account; actions move the
 * journey along (pick an idea → script → storyboard → caption; simulate → re-run) instead of
 * calling a server. On by default on Vercel when API_ORIGIN isn't set (next.config.mjs).
 */
export const DEMO = process.env.NEXT_PUBLIC_DEMO_MODE === 'true';

type Fixtures = {
  get: Record<string, any>;
  billing_free: any;
  validate: any;
  project_started: { project_id: string; job_id: string };
  project_stages: Record<'ideas' | 'script' | 'storyboard' | 'caption', any>;
  simulations: { take1: any; take2: any };
  agents: Record<string, any>;
  agent_replies: Record<string, string>;
  // v2.1
  recaps: any[];
  recap: Record<string, any>;
  share_image: Record<string, string>;
  first_recap_id: string | null;
  // v2.2: the personas' reactions per Studio stage (and per idea: "idea:<id>"), and recorded
  // persona chat answers per persona and question kind.
  persona_reactions?: Record<string, any>;
  persona_chat?: Record<string, Record<string, string>>;
};

const ORDER = ['ideas', 'script', 'storyboard', 'caption'] as const;
type Stage = (typeof ORDER)[number];

let fixtures: Promise<Fixtures> | null = null;
const load = () => (fixtures ??= fetch('/demo/fixtures.json').then((r) => r.json()));

// What the visitor has done, kept for this browser tab.
type State = {
  stage: Stage;
  hashtags: string[] | null;
  chosen: number | null;
  saved: Record<string, boolean>;
  chats: Record<string, { role: string; content: string }[]>;
  plan: 'free' | 'pro';
  used: { project: number; simulation: number; chat: number };
  onboardStart?: number | null; // when the visitor entered a username (first-run progress)
  viewed?: Record<string, boolean>; // recaps they've watched
};
const KEY = 'curo.demo.state';
function state(): State {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    /* private mode */
  }
  return { stage: 'ideas', hashtags: null, chosen: null, saved: {}, chats: {}, plan: 'free', used: { project: 0, simulation: 0, chat: 0 } };
}
function save(s: State) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* private mode */
  }
}

const clone = <T>(x: T): T => JSON.parse(JSON.stringify(x));
const job = (id = 'demo-job') => ({ id, type: 'demo', status: 'succeeded', progress: {}, result: {}, error: null, created_at: new Date().toISOString(), finished_at: new Date().toISOString() });

export class DemoError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(typeof detail === 'string' ? detail : 'Not available in the demo');
  }
}

function project(f: Fixtures, s: State) {
  const p = clone(f.project_stages[s.stage]);
  if (p.captions) {
    if (s.hashtags) p.captions.hashtags = s.hashtags;
    if (s.chosen !== null) p.captions.chosen = s.chosen;
  }
  return p;
}

function advance(s: State, to: Stage) {
  if (ORDER.indexOf(to) > ORDER.indexOf(s.stage)) s.stage = to;
}

function billing(f: Fixtures, s: State) {
  const b = clone(f.billing_free);
  b.plan = s.plan;
  const pro = { project: 10, simulation: 10, chat: 100 } as const;
  for (const r of ['project', 'simulation', 'chat'] as const) {
    const c = b.credits[r];
    if (s.plan === 'pro') {
      c.plan_total = pro[r];
      c.plan_left = Math.max(0, pro[r] - s.used[r]);
    } else {
      c.plan_left = Math.max(0, c.plan_left - s.used[r]);
    }
    c.left = c.plan_left + c.topup_left;
  }
  return b;
}

/** Answer one API call from the recording. */
export async function demoApi(method: string, rawPath: string, body: any): Promise<any> {
  const f = await load();
  const s = state();
  const path = rawPath.split('?')[0];
  const m = (re: RegExp) => path.match(re);
  const done = (out: any) => {
    save(s);
    return out;
  };

  if (method === 'GET') {
    if (path === '/billing') return billing(f, s);
    if (path === '/admin/costs') throw new DemoError(404, 'Not found');
    if (path === '/chat') return [];
    if (path === '/onboarding/status') return onboarding(f, s);
    if (path === '/me') {
      const me = clone(f.get['/me']);
      me.is_anonymous = anonymous();
      if (me.is_anonymous) me.email = null;
      return me;
    }
    if (path === '/recaps/latest') {
      const latest = [...f.recaps].sort((a, b) => (a.period_end < b.period_end ? 1 : -1))[0];
      return latest ? withSeen(f.recap[latest.id], s) : null;
    }
    if (path === '/recaps') return f.recaps.map((r: any) => withSeen(r, s));
    const share = m(/^\/recaps\/([^/]+)\/share-image$/);
    if (share) return f.share_image[share[1]] ?? '';
    const one = m(/^\/recaps\/([^/]+)$/);
    if (one) {
      if (!f.recap[one[1]]) throw new DemoError(404, 'Recap not found');
      return withSeen(f.recap[one[1]], s);
    }
    if (m(/^\/jobs\//)) return job(path.split('/')[2]);
    const pchat = m(/^\/personas\/([^/]+)\/chat$/);
    if (pchat) return s.chats[`persona:${pchat[1]}`] ?? [];
    if (m(/^\/projects\/[^/]+\/persona-reactions$/)) {
      const all = f.persona_reactions ?? {};
      return clone(all[s.stage] ?? { status: 'none', reactions: [], label: '' });
    }
    if (m(/^\/projects\/[^/]+$/)) return project(f, s);
    if (m(/^\/opportunities\/[^/]+$/)) {
      const o = clone(f.get[path]);
      if (!o) throw new DemoError(404, 'Not found');
      if (o.id in s.saved) o.saved = s.saved[o.id];
      return o;
    }
    if (path === '/opportunities') return clone(f.get[path]).map((o: any) => (o.id in s.saved ? { ...o, saved: s.saved[o.id] } : o));
    const sim = m(/^\/simulations\/([^/]+)$/);
    if (sim) {
      const found = [f.simulations.take1, f.simulations.take2].find((x) => x.id === sim[1]);
      if (!found) throw new DemoError(404, 'Simulation not found');
      return found;
    }
    const agent = m(/^\/simulations\/([^/]+)\/agents\/(\d+)$/);
    if (agent) {
      const a = clone(f.agents[`${agent[1]}:${agent[2]}`]);
      if (!a) throw new DemoError(404, 'Agent not found');
      const chat = s.chats[`${agent[1]}`] ?? [];
      a.chat = s.chats[`${agent[1]}:${agent[2]}`] ?? [];
      a.messages_left = 10 - chat.length;
      return a;
    }
    if (path in f.get) return clone(f.get[path]);
    throw new DemoError(404, 'Not in the demo');
  }

  // ---------------------------------------------------------------- actions
  if (path === '/reels/refresh') return { status: 'fresh', last_snapshot_at: null };
  if (m(/^\/projects\/[^/]+\/persona-reactions$/)) {
    const all = f.persona_reactions ?? {};
    const key = body?.target_id ? `idea:${body.target_id}` : s.stage;
    return clone(all[key] ?? all[s.stage] ?? { status: 'none', reactions: [], label: '' });
  }
  const saveOpp = m(/^\/opportunities\/([^/]+)\/save$/);
  if (saveOpp) {
    s.saved[saveOpp[1]] = method === 'POST';
    const card = f.get['/opportunities'].find((o: any) => o.id === saveOpp[1]);
    return done({ ...card, saved: method === 'POST' });
  }
  if (m(/^\/opportunities\/[^/]+\/dismiss$/)) return undefined;
  if (path === '/ideas/validate') return { ...clone(f.validate), text: body?.text ?? f.validate.text };
  if (path === '/projects' && method === 'POST') {
    s.stage = 'ideas';
    s.hashtags = null;
    s.chosen = null;
    s.used.project += 1;
    return done(clone(f.project_started));
  }
  if (m(/\/ideas\/[^/]+\/select$/)) {
    advance(s, 'script');
    return done(project(f, s));
  }
  if (m(/\/ideas$/)) return done({ project_id: f.project_started.project_id, job_id: 'demo-job' });
  if (m(/\/script(\/revise)?$/)) {
    advance(s, 'script');
    return done(method === 'PUT' ? project(f, s) : { project_id: f.project_started.project_id, job_id: 'demo-job' });
  }
  if (m(/\/storyboard(\/revise)?$/)) {
    advance(s, 'storyboard');
    return done({ project_id: f.project_started.project_id, job_id: 'demo-job' });
  }
  if (m(/\/captions(\/revise)?$/)) {
    advance(s, 'caption');
    return done({ project_id: f.project_started.project_id, job_id: 'demo-job' });
  }
  if (m(/\/hashtags$/)) {
    if ((body?.hashtags ?? []).length > 5) throw new DemoError(422, 'At most five hashtags.');
    s.hashtags = body.hashtags;
    return done(project(f, s));
  }
  if (m(/\/caption$/)) {
    s.chosen = body?.chosen ?? null;
    return done(project(f, s));
  }
  if (m(/^\/projects\/[^/]+\/save$/)) return project(f, s);
  if (path === '/uploads/sample') {
    const v = f.get['/uploads/samples'].find((x: any) => x.name === body?.name) ?? f.get['/uploads/samples'][0];
    return { path: `demo/${v.name}`, caption: v.caption, duration_s: v.duration_s, width: v.width, height: v.height };
  }
  if (path === '/uploads/sign') return { path: 'demo/upload', url: '', method: 'PUT', headers: {}, expires_at: new Date().toISOString() };
  if (path === '/simulations') {
    s.used.simulation += 1;
    return done({ simulation_id: f.simulations.take1.id, job_id: 'demo-job' });
  }
  if (m(/^\/simulations\/[^/]+\/rerun$/)) {
    s.used.simulation += 1;
    return done({ simulation_id: f.simulations.take2.id, job_id: 'demo-job' });
  }
  const apply = m(/^\/simulations\/([^/]+)\/edits\/([^/]+)\/apply$/);
  if (apply) {
    const sim = [f.simulations.take1, f.simulations.take2].find((x) => x.id === apply[1]);
    const edit = (sim?.edits ?? []).find((e: any) => e.id === apply[2]);
    return { edit: { ...edit, applied: true }, job_id: null };
  }
  const talk = m(/^\/simulations\/([^/]+)\/agents\/(\d+)\/chat$/);
  if (talk) {
    const used = s.chats[talk[1]] ?? [];
    if (used.length >= 10) {
      throw new DemoError(402, { code: 'agent_chat_limit', message: 'This simulation has used its 10 agent messages.' });
    }
    const q: string = body?.message ?? '';
    const replies = f.agent_replies;
    const key = /why|stop|skip/i.test(q)
      ? 'Why did you stop watching?'
      : /share|send/i.test(q)
        ? 'What would make you share this?'
        : 'What should I change?';
    const answer = replies[key] ?? Object.values(replies)[0] ?? 'I watched it through.';
    const k = `${talk[1]}:${talk[2]}`;
    s.chats[k] = [...(s.chats[k] ?? []), { role: 'user', content: q }, { role: 'agent', content: answer }];
    s.chats[talk[1]] = [...used, { role: 'user', content: q }];
    return done({ answer, messages_left: 10 - s.chats[talk[1]].length });
  }
  if (path === '/billing/checkout') {
    if (body?.item === 'pro') s.plan = 'pro';
    save(s);
    return { status: 'completed', ref: 'demo', url: null, billing: billing(f, s) };
  }
  if (path === '/billing/cancel') {
    s.plan = 'free';
    return done(billing(f, s));
  }
  if (m(/^\/memory\//)) return undefined;
  if (path === '/me' && method === 'DELETE') {
    sessionStorage.removeItem(KEY);
    return { status: 'deleted', job_id: null };
  }
  if (path === '/onboarding/username') {
    s.onboardStart = Date.now();
    return done({ job_id: 'demo-job', username: 'curo.demo' });
  }
  const viewed = m(/^\/recaps\/([^/]+)\/viewed$/);
  if (viewed) {
    s.viewed = { ...(s.viewed ?? {}), [viewed[1]]: true };
    const r = f.recaps.find((x: any) => x.id === viewed[1]);
    return done(withSeen(r, s));
  }
  throw new DemoError(501, 'This isn’t available in the demo.');
}

/** Ask Curo in the demo: one honest, canned reply (the assistant needs the backend). */
export async function* demoChat(): AsyncGenerator<{ event: string; data: any }> {
  const s = state();
  s.used.chat += 1;
  save(s);
  const text =
    'This is the demo, so Ask Curo isn’t connected to a server. With the backend running, it answers from your own reels and comments and can change any Studio step for you.';
  for (const word of text.split(' ')) {
    await new Promise((r) => setTimeout(r, 25));
    yield { event: 'delta', data: { text: `${word} ` } };
  }
  yield { event: 'done', data: { text } };
}

/** Persona chat in the demo: answers recorded from the real T28 for a few kinds of question. */
export async function* demoPersonaChat(personaId: string, message: string): AsyncGenerator<{ event: string; data: any }> {
  const f = await load();
  const s = state();
  s.used.chat += 1;
  const answers = f.persona_chat?.[personaId] ?? {};
  const kind = /how many|exact|who|real|age|old/i.test(message)
    ? 'honest'
    : /share|send/i.test(message)
      ? 'share'
      : /why|skip|scroll/i.test(message)
        ? 'why'
        : 'next';
  const text =
    answers[kind] ?? Object.values(answers)[0] ?? 'I’m a summary of your comments. In the demo I can only give recorded answers.';
  const k = `persona:${personaId}`;
  const now = new Date().toISOString();
  s.chats[k] = [
    ...(s.chats[k] ?? []),
    { id: `u${Date.now()}`, role: 'user', content: message, created_at: now } as any,
    { id: `p${Date.now()}`, role: 'persona', content: text, created_at: now } as any,
  ];
  save(s);
  for (const word of text.split(' ')) {
    await new Promise((r) => setTimeout(r, 25));
    yield { event: 'delta', data: { text: `${word} ` } };
  }
  yield { event: 'done', data: { text } };
}


// ---------------------------------------------------------------- v2.1 first run

function anonymous(): boolean {
  try {
    const raw = window.localStorage.getItem('curo.session');
    return !(raw && JSON.parse(raw).email);
  } catch {
    return true;
  }
}

function withSeen(r: any, s: State) {
  if (!r) return r;
  const seen = !!s.viewed?.[r.id];
  return { ...clone(r), is_new: !seen, viewed_at: seen ? new Date().toISOString() : null };
}

/** The first run's progress strip, played out over about ten seconds. */
function onboarding(f: Fixtures, s: State) {
  const base = { username: 'curo.demo', followers: f.get['/me']?.account?.followers ?? null, reels_processed: 30 };
  if (!s.onboardStart) {
    return { ...base, status: 'ready', step: 'recap_ready', reels_found: 50, comments_done: 30, comments_total: 30, recap_id: f.first_recap_id, recap_status: 'ready' };
  }
  const t = (Date.now() - s.onboardStart) / 1000;
  if (t < 2) return { ...base, status: 'running', step: 'profile', reels_found: 0, comments_done: 0, comments_total: 0 };
  if (t < 4) return { ...base, status: 'running', step: 'reels', reels_found: 0, comments_done: 0, comments_total: 0 };
  if (t < 7) return { ...base, status: 'running', step: 'comments', reels_found: 50, comments_done: Math.round((t - 4) * 10), comments_total: 30 };
  if (t < 10) return { ...base, status: 'running', step: 'recap', reels_found: 50, comments_done: 30, comments_total: 30, recap_id: f.first_recap_id, recap_status: 'building' };
  return { ...base, status: 'ready', step: 'recap_ready', reels_found: 50, comments_done: 30, comments_total: 30, recap_id: f.first_recap_id, recap_status: 'ready' };
}
