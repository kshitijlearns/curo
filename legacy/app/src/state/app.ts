/**
 * App state for the main shell: navigation, the Studio's screen state and the Simulator's.
 * Ported from the prototype's single component (its methods became actions).
 *
 * The Studio's data — ideas, script, storyboard, captions — lives on the API under one project
 * id (read with `useProject`); this store keeps only what's on screen: the project, the step,
 * what's picked or open, and what's being worked on. Studio actions call `@/api/studio` and
 * the cached project updates when each step finishes. The Simulator works the same way: its
 * result lives on the API under one simulation id (`useSimulation`); this store keeps the
 * upload, the audience on screen and what's picked or open.
 *
 * Every chat box sends to Ask Curo (`askCuro`). The API decides what the message is: a
 * change on a Studio screen comes back as a handoff and goes to that step's own action; a
 * question, a what-if or a preference is answered in the screen's thread, streamed.
 */
import { create } from 'zustand';

import * as chatApi from '@/api/chat';
import { waitForJob } from '@/api/jobs';
import * as simApi from '@/api/simulator';
import * as studio from '@/api/studio';
import type { Tab } from '@/components/Nav';
import { SIM_STEPS, type Audience, type DnaTab } from '@/lib/simText';

/* ------------------------------------------------------------------ types */

export type HomeView = 'home' | 'insights' | 'opportunity';
export type StudioStage = 'ideas' | 'idea' | 'script' | 'storyboard' | 'caption' | 'final';
export type ValidationTurn = {
  id: number;
  text: string;
  result: studio.Validation | null;
  error?: string | null;
};
export type Busy = 'ideas' | 'script' | 'storyboard' | 'caption' | 'save' | null;

export type StudioState = {
  projectId: string | null;
  /** The opportunity it came from, shown while its first ideas are written. */
  oppName: string | null;
  /** The chosen idea's words (the Simulator links to it). */
  ideaTitle: string | null;
  stage: StudioStage;
  maxStep: number;
  pick: string | null;
  openWhy: string | null;
  validations: ValidationTurn[];
  busy: Busy;
  /** The creator's words while their request is being worked on. */
  sent: string | null;
  /** A note sent for a new round of ideas, until the round arrives. */
  pendingRound: string | null;
  openNote: string | null;
  frame: number;
  busyFrame: number | null;
  tagNudge: string | null;
};

export type SimUpload = {
  path: string;
  name: string;
  durationS: number;
  width: number | null;
  height: number | null;
  /** A sample recording's caption (sent when no linked draft has a chosen caption). */
  caption: string | null;
};

export type SimState = {
  view: 'intro' | 'loading' | 'result';
  audience: Audience;
  /** Edits picked to apply, by id. */
  pending: Record<string, boolean>;
  step: number;
  dnaTab: DnaTab;
  openEv: Record<string, boolean>;
  uploading: boolean;
  upload: SimUpload | null;
  linked: boolean;
  /** The simulation on screen. */
  simulationId: string | null;
  /** Accepted edits are being written back to the draft. */
  applying: boolean;
  /** Edits applied: the next step is the re-recorded take. */
  awaitingTake: boolean;
};

/* ------------------------------------------------------------------ helpers */

export const STEP_OF: Record<StudioStage, number> = {
  ideas: 0,
  idea: 1,
  script: 1,
  storyboard: 2,
  caption: 3,
  final: 4,
};
const MAX_HASHTAGS = 5;

export function freshStudio(): StudioState {
  return {
    projectId: null,
    oppName: null,
    ideaTitle: null,
    stage: 'ideas',
    maxStep: 0,
    pick: null,
    openWhy: null,
    validations: [],
    busy: null,
    sent: null,
    pendingRound: null,
    openNote: null,
    frame: 0,
    busyFrame: null,
    tagNudge: null,
  };
}

export const freshSim = (): SimState => ({
  view: 'intro',
  audience: 'both',
  pending: {},
  step: 0,
  dnaTab: 'content',
  openEv: {},
  uploading: false,
  upload: null,
  linked: true,
  simulationId: null,
  applying: false,
  awaitingTake: false,
});

/** Where a project's work has got to, as the furthest step reached. */
function reached(p: studio.Project): number {
  if (p.captions) return 3;
  if (p.storyboard) return 2;
  if (p.idea) return 1;
  return 0;
}

/** A creator's own script, pasted in, rather than a request: several lines, or a long text. */
export function looksLikeScript(text: string): boolean {
  const lines = text.split('\n').filter((l) => l.trim());
  return lines.length >= 2 || text.trim().split(/\s+/).length >= 20;
}

export function simLinked(s: { sim: SimState; studio: StudioState }): boolean {
  return s.sim.linked && !!s.studio.projectId && !!s.studio.ideaTitle;
}

/** Why a picked video can't be simulated (too long), or null. */
export function tooLong(video: simApi.PickedVideo): string | null {
  if (video.durationS == null || video.durationS <= simApi.MAX_SECONDS + 0.5) return null;
  return `That video is ${Math.round(video.durationS)} seconds long. The Simulator takes reels of up to ${simApi.MAX_SECONDS} seconds.`;
}

const toUpload = (u: simApi.Uploaded, name: string): SimUpload => ({
  path: u.path,
  name,
  durationS: u.duration_s,
  width: u.width ?? null,
  height: u.height ?? null,
  caption: u.caption ?? null,
});

/* ------------------------------------------------------------------ Ask Curo */

export type ChatMsg = {
  id: string;
  role: 'user' | 'curo';
  text: string;
  sources?: chatApi.ChatSource[];
  /** Still arriving. */
  pending?: boolean;
  /** What Curo is doing while a tool runs ("Looking through your reels…"). */
  activity?: string | null;
  failed?: boolean;
};

export type ChatTarget = {
  key: string;
  screen: chatApi.ChatScreen;
  project_id: string | null;
  simulation_id: string | null;
  frame_id: string | null;
};

/** Where a composer message goes: the screen, what's open on it, and the thread it shows in. */
export function chatTarget(
  s: Pick<AppState, 'tab' | 'overlay' | 'studio' | 'sim'>,
  frameId: string | null = null,
): ChatTarget | null {
  if (s.overlay) return null;
  if (s.tab === 'studio') {
    const st = s.studio;
    if (!st.projectId)
      return {
        key: 'studio:validate',
        screen: 'studio:validate',
        project_id: null,
        simulation_id: null,
        frame_id: null,
      };
    if (st.stage === 'final') return null;
    return {
      key: `studio:${st.projectId}:${st.stage}`,
      screen: `studio:${st.stage}` as chatApi.ChatScreen,
      project_id: st.projectId,
      simulation_id: null,
      frame_id: st.stage === 'storyboard' ? frameId : null,
    };
  }
  if (s.tab === 'sim' && s.sim.view === 'result' && s.sim.simulationId)
    return {
      key: `sim:${s.sim.simulationId}`,
      screen: 'sim:result',
      project_id: null,
      simulation_id: s.sim.simulationId,
      frame_id: null,
    };
  return null;
}

let msgSeq = 0;
const msgId = () => `m${Date.now().toString(36)}${(msgSeq++).toString(36)}`;

/* ------------------------------------------------------------------ store */

type ScrollReq = { kind: 'top' | 'bottom'; n: number };

export type AppState = {
  tab: Tab;
  homeView: HomeView;
  reelIdx: number;
  /** The opportunity shown on Home's pager (an API id; '' until one is opened). */
  oppId: string;
  overlay: 'saved' | null;
  studio: StudioState;
  sim: SimState;
  toast: { id: number; text: string } | null;
  scroll: ScrollReq;

  // shell
  nav: (tab: Tab) => void;
  showToast: (text: string) => void;
  scrollTop: () => void;
  scrollBottom: () => void;
  // home
  goReel: (i: number) => void;
  openInsights: (i: number) => void;
  goHomeRoot: () => void;
  openOpp: (id: string) => void;
  setOpp: (id: string) => void;
  openInStudio: (opportunityId: string, name: string) => Promise<void>;
  // saved (saving opportunities goes through the API: useSaveOpportunity)
  openSaved: () => void;
  closeSaved: () => void;
  openSavedOpp: (id: string) => void;
  openDraft: (projectId: string) => Promise<void>;
  // studio
  pickIdea: (ideaId: string) => void;
  toggleWhy: (ideaId: string) => void;
  continueIdea: () => Promise<void>;
  sendIdeas: (text: string) => Promise<void>;
  validate: (text: string) => Promise<void>;
  developValidated: (turn: ValidationTurn) => Promise<void>;
  generateScript: (direction: string | null) => Promise<void>;
  regenerate: () => Promise<void>;
  scriptSend: (text: string) => Promise<void>;
  toggleNote: (beatId: string) => void;
  toStoryboard: () => Promise<void>;
  goFrame: (i: number) => void;
  sbSend: (text: string) => Promise<void>;
  toCaption: () => Promise<void>;
  capSend: (text: string) => Promise<void>;
  pickCaption: (i: number) => Promise<void>;
  toggleTag: (tag: string) => Promise<void>;
  toFinal: () => void;
  skipToFinal: () => Promise<void>;
  editScript: () => Promise<void>;
  goStep: (i: number) => void;
  saveDraft: () => Promise<void>;
  // simulator
  uploadPicked: (video: simApi.PickedVideo) => Promise<void>;
  uploadSample: (name: string, title: string) => Promise<void>;
  replaceUpload: () => void;
  toggleLink: () => void;
  setAudience: (a: Audience) => void;
  setDnaTab: (t: DnaTab) => void;
  runSim: () => Promise<void>;
  toggleEdit: (id: string) => void;
  editRerun: () => Promise<void>;
  rerunPicked: (video: simApi.PickedVideo) => Promise<void>;
  rerunSample: (name: string, title: string) => Promise<void>;
  toggleSimEv: (key: string) => void;
  viewFrame: (i: number) => void;
  backToIntro: () => void;
  publish: () => void;
  discard: () => void;
  // Ask Curo: one thread per screen (a Studio step of a draft, or a simulation)
  chat: Record<string, ChatMsg[]>;
  asking: string | null;
  askCuro: (text: string) => Promise<void>;
  loadThread: (simulationId: string) => Promise<void>;
  // composer
  composerSend: (text: string) => void;
};

let toastTimer: ReturnType<typeof setTimeout> | undefined;
const later = (ms: number, fn: () => void) => setTimeout(fn, ms);
const message = (e: unknown) =>
  e instanceof Error && e.message ? e.message : 'That didn’t work. Try again.';

export const useApp = create<AppState>()((set, get) => {
  const S = (patch: Partial<StudioState> | ((st: StudioState) => Partial<StudioState>)) =>
    set((s) => ({
      studio: { ...s.studio, ...(typeof patch === 'function' ? patch(s.studio) : patch) },
    }));
  const M = (patch: Partial<SimState> | ((sim: SimState) => Partial<SimState>)) =>
    set((s) => ({ sim: { ...s.sim, ...(typeof patch === 'function' ? patch(s.sim) : patch) } }));
  const project = () => studio.cachedProject(get().studio.projectId);
  const simulation = () => simApi.cachedSimulation(get().sim.simulationId);
  const C = (key: string, fn: (msgs: ChatMsg[]) => ChatMsg[]) =>
    set((s) => ({ chat: { ...s.chat, [key]: fn(s.chat[key] ?? []) } }));
  const R = (key: string, id: string, patch: (m: ChatMsg) => Partial<ChatMsg>) =>
    C(key, (msgs) => msgs.map((m) => (m.id === id ? { ...m, ...patch(m) } : m)));

  /** A change on a Studio screen, applied by that step (the API handed it back). */
  const studioChange = (text: string) => {
    const s = get();
    const st = s.studio;
    if (!st.projectId) return s.validate(text);
    if (st.stage === 'ideas') return s.sendIdeas(text);
    if (st.stage === 'idea') return s.generateScript(text);
    if (st.stage === 'script') return s.scriptSend(text);
    if (st.stage === 'storyboard') return s.sbSend(text);
    if (st.stage === 'caption') return s.capSend(text);
  };

  /** A change Ask Curo made as a job: follow it, then show the new draft. */
  const followJob = async (job: chatApi.ChatJob, projectId: string | null) => {
    const done = await waitForJob(job.job_id, { intervalMs: 600, timeoutMs: 180_000 });
    if (done.status === 'failed') throw new Error(done.error ?? 'That change didn’t go through.');
    if (projectId) await studio.getProject(projectId);
    get().showToast(
      job.step === 'storyboard'
        ? 'Storyboard updated in your Studio draft.'
        : 'Script updated in your Studio draft.',
    );
  };

  /** The caption sent with an upload: none when the linked draft has its own chosen caption
   * (the API then uses that one). */
  const captionFor = (upload: SimUpload): string | null => {
    const p = project();
    return simLinked(get()) && p?.captions?.chosen != null ? null : upload.caption;
  };

  const showResult = (simulationId: string) => {
    M({
      view: 'result',
      simulationId,
      step: SIM_STEPS.length,
      pending: {},
      openEv: {},
      awaitingTake: false,
    });
    get().scrollTop();
    void get().loadThread(simulationId);
  };

  /** Upload the re-recorded take and simulate it against the run on screen. */
  const rerunWith = async (make: () => Promise<SimUpload>) => {
    const id = get().sim.simulationId;
    if (!id || get().sim.uploading) return;
    M({ uploading: true });
    let upload: SimUpload;
    try {
      upload = await make();
    } catch (e) {
      M({ uploading: false });
      get().showToast(message(e));
      return;
    }
    M({ uploading: false, upload, view: 'loading', step: 0 });
    get().scrollTop();
    try {
      const sim = await simApi.rerun(
        id,
        { upload_path: upload.path, caption: captionFor(upload) },
        (step) => M({ step }),
      );
      showResult(sim.id);
    } catch (e) {
      M({ view: 'result' });
      get().showToast(message(e));
    }
  };

  /** Run a Studio step: mark it busy, show any failure as a toast, always clear the mark. */
  const run = async (busy: Busy, fn: (projectId: string) => Promise<unknown>, sent?: string) => {
    const id = get().studio.projectId;
    if (!id || get().studio.busy) return;
    S({ busy, sent: sent ?? null });
    try {
      await fn(id);
    } catch (e) {
      get().showToast(message(e));
    } finally {
      S({ busy: null, sent: null, busyFrame: null, pendingRound: null });
    }
  };

  return {
    tab: 'home',
    homeView: 'home',
    reelIdx: 0,
    oppId: '',
    overlay: null,
    studio: freshStudio(),
    sim: freshSim(),
    toast: null,
    scroll: { kind: 'top', n: 0 },

    /* -------------------------------------------------------------- shell */
    nav: (tab) => {
      const s = get();
      if (tab === s.tab)
        set(tab === 'home' ? { homeView: 'home', overlay: null } : { overlay: null });
      else set({ tab, overlay: null });
      get().scrollTop();
    },
    showToast: (text) => {
      const id = Date.now();
      set({ toast: { id, text } });
      if (toastTimer) clearTimeout(toastTimer);
      toastTimer = later(2800, () => {
        if (get().toast?.id === id) set({ toast: null });
      });
    },
    scrollTop: () => set((s) => ({ scroll: { kind: 'top', n: s.scroll.n + 1 } })),
    scrollBottom: () =>
      later(80, () => set((s) => ({ scroll: { kind: 'bottom', n: s.scroll.n + 1 } }))),

    /* -------------------------------------------------------------- home */
    goReel: (i) => set({ reelIdx: i }),
    openInsights: (i) => {
      set({ homeView: 'insights', reelIdx: i });
      get().scrollTop();
    },
    goHomeRoot: () => {
      set({ homeView: 'home' });
      get().scrollTop();
    },
    openOpp: (id) => {
      set({ homeView: 'opportunity', oppId: id });
      get().scrollTop();
    },
    setOpp: (id) => set({ oppId: id }),
    openInStudio: async (opportunityId, name) => {
      // A new project from the opportunity; Home's selected opportunity stays.
      set({
        tab: 'studio',
        overlay: null,
        studio: { ...freshStudio(), oppName: name, busy: 'ideas' },
      });
      get().scrollTop();
      try {
        const p = await studio.startProject({ opportunity_id: opportunityId });
        S({ projectId: p.id });
      } catch (e) {
        get().showToast(message(e));
        S({ oppName: null });
      } finally {
        S({ busy: null });
      }
    },

    /* -------------------------------------------------------------- saved */
    openSaved: () => {
      set({ overlay: 'saved' });
      get().scrollTop();
    },
    closeSaved: () => {
      set({ overlay: null });
      get().scrollTop();
    },
    openSavedOpp: (id) => {
      set({ overlay: null, tab: 'home', homeView: 'opportunity', oppId: id });
      get().scrollTop();
    },
    openDraft: async (projectId) => {
      try {
        const p = await studio.getProject(projectId);
        set({
          overlay: null,
          tab: 'studio',
          studio: {
            ...freshStudio(),
            projectId,
            oppName: p.opportunity?.name ?? null,
            ideaTitle: p.idea?.text ?? null,
            pick: p.idea?.id ?? null,
            stage: p.step === 'idea' && p.script ? 'script' : p.step,
            maxStep: Math.max(reached(p), STEP_OF[p.step]),
          },
        });
        get().scrollTop();
      } catch (e) {
        get().showToast(message(e));
      }
    },

    /* -------------------------------------------------------------- studio: ideas */
    pickIdea: (ideaId) => S({ pick: ideaId }),
    toggleWhy: (ideaId) => S((st) => ({ openWhy: st.openWhy === ideaId ? null : ideaId })),
    continueIdea: async () => {
      const st = get().studio;
      if (!st.pick) return;
      await run('ideas', async (id) => {
        const p = await studio.selectIdea(id, st.pick!);
        S({
          ideaTitle: p.idea?.text ?? null,
          stage: p.script ? 'script' : 'idea',
          maxStep: Math.max(get().studio.maxStep, 1, reached(p)),
          frame: 0,
          openNote: null,
        });
      });
      get().scrollTop();
    },
    sendIdeas: async (text) => {
      S({ pendingRound: text, pick: null });
      get().scrollBottom();
      await run('ideas', (id) => studio.newIdeas(id, text), text);
      get().scrollBottom();
    },
    validate: async (text) => {
      const id = Date.now();
      S((st) => ({ validations: [...st.validations, { id, text, result: null }] }));
      get().scrollBottom();
      try {
        const result = await studio.validateIdea(text);
        S((st) => ({
          validations: st.validations.map((v) => (v.id === id ? { ...v, result } : v)),
        }));
      } catch (e) {
        S((st) => ({
          validations: st.validations.map((v) => (v.id === id ? { ...v, error: message(e) } : v)),
        }));
      }
      get().scrollBottom();
    },
    developValidated: async (turn) => {
      if (!turn.result) return;
      S({ busy: 'ideas' });
      try {
        const p = await studio.startProject({ idea_text: turn.result.text });
        set({
          studio: {
            ...freshStudio(),
            projectId: p.id,
            ideaTitle: p.idea?.text ?? turn.result.text,
            pick: p.idea?.id ?? null,
            stage: 'idea',
            maxStep: 1,
          },
        });
        get().scrollTop();
      } catch (e) {
        get().showToast(message(e));
        S({ busy: null });
      }
    },

    /* -------------------------------------------------------------- studio: script */
    generateScript: async (direction) => {
      if (direction && looksLikeScript(direction)) return get().scriptSend(direction);
      S((st) => ({ stage: 'script', maxStep: Math.max(st.maxStep, 1), openNote: null }));
      get().scrollTop();
      await run('script', (id) => studio.writeScript(id, { direction }), direction ?? undefined);
    },
    regenerate: async () => {
      if (!project()?.script) return get().generateScript(null);
      S({ openNote: null });
      await run('script', (id) => studio.writeScript(id, { regenerate: true }));
    },
    scriptSend: async (text) => {
      S((st) => ({ stage: 'script', maxStep: Math.max(st.maxStep, 1), openNote: null }));
      if (looksLikeScript(text)) {
        // "Dump your script idea here": kept as written, split into beats, notes added.
        await run('script', (id) => studio.ownScript(id, text), text);
        return;
      }
      if (!project()?.script) {
        await run('script', (id) => studio.writeScript(id, { direction: text }), text);
        return;
      }
      await run('script', (id) => studio.reviseScript(id, text), text);
    },
    toggleNote: (beatId) => S((st) => ({ openNote: st.openNote === beatId ? null : beatId })),

    /* -------------------------------------------------------------- studio: storyboard */
    toStoryboard: async () => {
      S((st) => ({ stage: 'storyboard', maxStep: Math.max(st.maxStep, 2), frame: 0 }));
      get().scrollTop();
      const p = project();
      if (!p?.script) return;
      if (!p.storyboard || !p.storyboard.up_to_date)
        await run('storyboard', (id) => studio.buildStoryboard(id));
    },
    goFrame: (i) => S({ frame: i }),
    sbSend: async (text) => {
      const st = get().studio;
      const frames = project()?.storyboard?.frames ?? [];
      const current = frames[Math.min(st.frame, Math.max(frames.length - 1, 0))];
      S({ busyFrame: st.frame });
      await run('storyboard', (id) => studio.reviseStoryboard(id, text, current?.id ?? null), text);
    },

    /* -------------------------------------------------------------- studio: caption + final */
    toCaption: async () => {
      S((st) => ({ stage: 'caption', maxStep: Math.max(st.maxStep, 3) }));
      get().scrollTop();
      const p = project();
      if (p?.script && !p.captions) await run('caption', (id) => studio.writeCaptions(id));
    },
    capSend: async (text) => {
      await run('caption', (id) => studio.reviseCaptions(id, text), text);
    },
    pickCaption: async (i) => {
      const id = get().studio.projectId;
      if (!id) return;
      try {
        await studio.chooseCaption(id, i);
      } catch (e) {
        get().showToast(message(e));
      }
    },
    toggleTag: async (tag) => {
      const id = get().studio.projectId;
      const tags = project()?.captions?.hashtags ?? [];
      if (!id) return;
      const on = tags.includes(tag);
      if (!on && tags.length >= MAX_HASHTAGS) {
        get().showToast('You can pick up to 5 hashtags. Remove one to add another.');
        S({ tagNudge: tag });
        later(500, () => S({ tagNudge: null }));
        return;
      }
      try {
        await studio.putHashtags(id, on ? tags.filter((t) => t !== tag) : [...tags, tag]);
      } catch (e) {
        get().showToast(message(e));
      }
    },
    toFinal: () => {
      S({ stage: 'final', maxStep: 4 });
      get().scrollTop();
    },
    skipToFinal: async () => {
      const st = get().studio;
      const p = project();
      if (!p?.idea) {
        const pick = st.pick ?? p?.rounds?.[p.rounds.length - 1]?.ideas[0]?.id;
        if (!pick || !st.projectId) return;
        try {
          const chosen = await studio.selectIdea(st.projectId, pick);
          S({ ideaTitle: chosen.idea?.text ?? null, pick });
        } catch (e) {
          get().showToast(message(e));
          return;
        }
      }
      get().toFinal();
    },
    editScript: async () => {
      if (project()?.script) {
        S({ stage: 'script' });
        get().scrollTop();
      } else await get().generateScript(null);
    },
    goStep: (i) => {
      const st = get().studio;
      if (i > st.maxStep) return;
      const p = project();
      if (i === 0) S({ stage: 'ideas' });
      else if (i === 1) S(p?.script ? { stage: 'script' } : p?.idea ? { stage: 'idea' } : {});
      else if (i === 2) void get().toStoryboard();
      else if (i === 3) void get().toCaption();
      else S({ stage: 'final' });
      get().scrollTop();
    },
    saveDraft: async () => {
      const st = get().studio;
      if (!project()?.idea) {
        get().showToast('Pick an idea first, then save your draft.');
        return;
      }
      await run('save', async (id) => {
        await studio.saveDraft(id, st.stage);
        get().showToast('Draft saved. Find it under Saved at the top.');
      });
    },

    /* -------------------------------------------------------------- simulator */
    uploadPicked: async (video) => {
      const long = tooLong(video);
      if (long) return get().showToast(long);
      M({ uploading: true, upload: null });
      try {
        M({ upload: toUpload(await simApi.uploadVideo(video), video.name) });
      } catch (e) {
        get().showToast(message(e));
      } finally {
        M({ uploading: false });
      }
    },
    uploadSample: async (name, title) => {
      M({ uploading: true, upload: null });
      try {
        M({ upload: toUpload(await simApi.uploadSample(name), title) });
      } catch (e) {
        get().showToast(message(e));
      } finally {
        M({ uploading: false });
      }
    },
    replaceUpload: () => M({ upload: null }),
    toggleLink: () => M((sim) => ({ linked: !sim.linked })),
    setAudience: (a) => M({ audience: a }),
    setDnaTab: (t) => M({ dnaTab: t }),
    runSim: async () => {
      const { upload, audience, view } = get().sim;
      if (!upload || view === 'loading') return;
      M({ view: 'loading', step: 0 });
      get().scrollTop();
      try {
        const sim = await simApi.runSimulation(
          {
            upload_path: upload.path,
            project_id: simLinked(get()) ? get().studio.projectId : null,
            audience,
            caption: captionFor(upload),
          },
          (step) => M({ step }),
        );
        showResult(sim.id);
      } catch (e) {
        M({ view: 'intro' });
        get().showToast(message(e));
      }
    },
    toggleEdit: (id) => M((sim) => ({ pending: { ...sim.pending, [id]: !sim.pending[id] } })),
    editRerun: async () => {
      const sim = simulation();
      const pending = get().sim.pending;
      const ids = Object.keys(pending).filter((k) => pending[k]);
      if (!sim || !ids.length || get().sim.applying) return;
      M({ applying: true });
      const projectId = sim.project_id ?? null;
      try {
        // One at a time: each accepted edit is a new version of the draft.
        for (const id of ids) await simApi.applyEdit(sim.id, id, projectId);
        await simApi.getSimulation(sim.id);
        M({ pending: {}, awaitingTake: true });
        get().showToast(
          projectId
            ? 'Edits written to your Studio script and storyboard. Re-record, then upload the new take.'
            : 'Edits noted. Re-record with these changes, then upload the new take.',
        );
      } catch (e) {
        get().showToast(message(e));
      } finally {
        M({ applying: false });
      }
    },
    rerunPicked: async (video) => {
      const long = tooLong(video);
      if (long) return get().showToast(long);
      await rerunWith(async () => toUpload(await simApi.uploadVideo(video), video.name));
    },
    rerunSample: (name, title) =>
      rerunWith(async () => toUpload(await simApi.uploadSample(name), title)),
    toggleSimEv: (key) => M((sim) => ({ openEv: { ...sim.openEv, [key]: !sim.openEv[key] } })),
    viewFrame: (i) => {
      const projectId = simulation()?.project_id;
      if (!projectId) {
        get().showToast('Link a Studio draft to jump to its storyboard frames.');
        return;
      }
      const open =
        get().studio.projectId === projectId ? Promise.resolve() : get().openDraft(projectId);
      void open
        .then(() => {
          set({ tab: 'studio' });
          return get().toStoryboard();
        })
        .then(() => S({ frame: i }));
    },
    backToIntro: () => {
      M({ view: 'intro' });
      get().scrollTop();
    },
    publish: () =>
      get().showToast(
        'Marked as ready to post. Curo doesn’t post to Instagram for you — post it from the Instagram app.',
      ),
    discard: () => {
      M((sim) => ({ ...freshSim(), audience: sim.audience, linked: sim.linked }));
      get().showToast('Simulation discarded. Your Studio draft is unchanged.');
      get().scrollTop();
    },

    /* -------------------------------------------------------------- Ask Curo */
    chat: {},
    asking: null,
    askCuro: async (text) => {
      const s = get();
      const frames = project()?.storyboard?.frames ?? [];
      const frame = frames[Math.min(s.studio.frame, Math.max(frames.length - 1, 0))];
      const target = chatTarget(s, frame?.id ?? null);
      if (!target || s.asking || (s.tab === 'studio' && s.studio.busy)) return;
      const user: ChatMsg = { id: msgId(), role: 'user', text };
      const reply: ChatMsg = { id: msgId(), role: 'curo', text: '', pending: true };
      C(target.key, (msgs) => [...msgs, user, reply]);
      set({ asking: target.key });
      s.scrollBottom();
      let handedOff = false;
      try {
        const done = await chatApi.sendChat(
          {
            message: text,
            screen: target.screen,
            project_id: target.project_id,
            simulation_id: target.simulation_id,
            frame_id: target.frame_id,
          },
          {
            meta: (m) => {
              if (m.handoff !== 'studio') return;
              handedOff = true; // the step shows the message itself
              C(target.key, (msgs) => msgs.filter((x) => x.id !== user.id && x.id !== reply.id));
            },
            tool: (name, status) =>
              R(target.key, reply.id, () => ({
                activity: status === 'running' ? (chatApi.TOOL_ACTIVITY[name] ?? null) : null,
              })),
            delta: (t) => R(target.key, reply.id, (m) => ({ text: m.text + t })),
            reset: () => R(target.key, reply.id, () => ({ text: '' })),
          },
        );
        set({ asking: null });
        if (handedOff || !done) {
          await studioChange(text);
          return;
        }
        R(target.key, reply.id, () => ({
          text: done.text,
          sources: done.sources,
          pending: false,
          activity: null,
        }));
        get().scrollBottom();
        const projectId = target.project_id ?? simulation()?.project_id ?? null;
        for (const job of done.jobs) await followJob(job, projectId);
      } catch (e) {
        if (handedOff) {
          get().showToast(message(e));
        } else {
          R(target.key, reply.id, () => ({
            text: message(e),
            pending: false,
            failed: true,
            activity: null,
          }));
        }
      } finally {
        set({ asking: null });
      }
    },
    loadThread: async (simulationId) => {
      try {
        const history = await chatApi.chatHistory(simulationId);
        const key = `sim:${simulationId}`;
        if (get().chat[key]?.length) return; // already talking here
        C(key, () =>
          history.map((m) => ({
            id: m.id,
            role: m.role === 'user' ? 'user' : 'curo',
            text: m.content,
            sources: m.sources,
          })),
        );
      } catch {
        // the conversation so far is a nicety; the screen works without it
      }
    },

    /* -------------------------------------------------------------- composer routing */
    composerSend: (text) => {
      if (get().overlay) return;
      void get().askCuro(text);
    },
  };
});
