import type { Simulation } from '@/api/simulator';
import type { Project } from '@/api/studio';
import { composerFor } from '@/screens/shell/composer';
import { freshSim, looksLikeScript, useApp } from '@/state/app';

/* A fake Studio API: mockProjects kept in memory, each call recorded. */
const mockCalls: { fn: string; args: unknown[] }[] = [];
const mockProjects = new Map<string, Project>();

function mockProject(over: Partial<Project> = {}): Project {
  return {
    id: 'p1',
    title: null,
    step: 'ideas',
    status: 'active',
    rounds: [],
    ...over,
  } as Project;
}

const mockIdea = {
  id: 'i1',
  text: 'Styling one outfit 3 ways for Ganpati',
  source: 'generated',
  selected: true,
};

jest.mock('@/api/studio', () => {
  const record =
    (fn: string, result: (...args: never[]) => unknown) =>
    async (...args: never[]) => {
      mockCalls.push({ fn, args });
      const out = await result(...args);
      if (out && typeof out === 'object' && 'id' in out)
        mockProjects.set((out as Project).id, out as Project);
      return out;
    };
  return {
    __esModule: true,
    startProject: record('startProject', (body: { idea_text?: string }) =>
      body.idea_text
        ? mockProject({
            step: 'idea',
            idea: { ...mockIdea, text: body.idea_text, source: 'creator' } as Project['idea'],
          })
        : mockProject({
            opportunity: { id: 'o1', name: 'Ganpati dress ideas', tag: 'Competitor' },
          }),
    ),
    getProject: record('getProject', (id: string) => mockProjects.get(id)),
    selectIdea: record('selectIdea', () =>
      mockProject({ step: 'idea', idea: mockIdea as Project['idea'] }),
    ),
    newIdeas: record('newIdeas', () => mockProjects.get('p1')),
    writeScript: record('writeScript', () => mockProjects.get('p1')),
    reviseScript: record('reviseScript', () => mockProjects.get('p1')),
    ownScript: record('ownScript', () => mockProjects.get('p1')),
    putHashtags: record('putHashtags', (_id: string, hashtags: string[]) => {
      const p = mockProjects.get('p1')!;
      return { ...p, captions: { ...p.captions!, hashtags } };
    }),
    chooseCaption: record('chooseCaption', () => mockProjects.get('p1')),
    saveDraft: record('saveDraft', () => mockProjects.get('p1')),
    validateIdea: record('validateIdea', (text: string) => ({
      text,
      score: 0.62,
      verdict: 'Worth trying',
      parts: { H: 0.6, A: 0.6, P: 0.6, T: 0.7, N: 0.5 },
      shares: { H: 34, A: 24, P: 19, T: 17, N: 6 },
      reasons: [],
      tweaks: [],
    })),
    buildStoryboard: record('buildStoryboard', () => mockProjects.get('p1')),
    writeCaptions: record('writeCaptions', () => mockProjects.get('p1')),
    cachedProject: (id: string | null) => (id ? mockProjects.get(id) : undefined),
  };
});

/* A fake Simulator API: simulations kept in memory, each call recorded in mockCalls too. */
const mockSims = new Map<string, Simulation>();

function mockSimulation(id: string, over: Partial<Simulation> = {}): Simulation {
  return {
    id,
    status: 'done',
    audience: 'both',
    project_id: 'p1',
    scores: { followers: 42, new: 50, both: 48 },
    score: 48,
    edits: [],
    created_at: '2027-08-23T04:30:00Z',
    ...over,
  } as Simulation;
}

jest.mock('@/api/simulator', () => {
  const record =
    (fn: string, result: (...args: never[]) => unknown) =>
    async (...args: never[]) => {
      mockCalls.push({ fn, args });
      const out = await result(...args);
      if (out && typeof out === 'object' && 'audience' in out)
        mockSims.set((out as Simulation).id, out as Simulation);
      return out;
    };
  const uploaded = (name: string) => ({
    path: `uploads/c1/${name}.mp4`,
    duration_s: name === 'take1' ? 41 : 32,
    width: 1080,
    height: 1920,
    caption: 'Same outfit, three looks for Ganpati #ganpatioutfit',
  });
  return {
    __esModule: true,
    MAX_SECONDS: 90,
    cachedSimulation: (id: string | null) => (id ? mockSims.get(id) : undefined),
    uploadSample: record('uploadSample', (name: string) => uploaded(name)),
    uploadVideo: record('uploadVideo', () => ({ ...uploaded('mine'), caption: null })),
    runSimulation: record(
      'runSimulation',
      (body: { upload_path: string }, onStep?: (n: number) => void) => {
        onStep?.(2);
        if (body.upload_path.includes('broken'))
          throw new Error(
            'This video is 95 seconds long. The Simulator takes reels of up to 90 seconds.',
          );
        return mockSimulation('s1');
      },
    ),
    rerun: record('rerun', () => mockSimulation('s2', { parent_simulation_id: 's1' })),
    applyEdit: record('applyEdit', (_sim: string, edit: string) => ({ id: edit, applied: true })),
    getSimulation: record('getSimulation', (id: string) => mockSims.get(id)),
  };
});

/* A fake Ask Curo: a question is answered (with a source); anything else is handed back to the
   Studio step, as the API's classifier does for a change on a Studio screen. */
jest.mock('@/api/chat', () => ({
  __esModule: true,
  TOOL_ACTIVITY: {},
  chatHistory: async () => [],
  sendChat: async (
    body: { message: string; screen: string },
    on: { meta?: (m: unknown) => void; delta?: (t: string) => void; reset?: () => void },
  ) => {
    mockCalls.push({ fn: 'sendChat', args: [body] });
    const question = body.message.trim().endsWith('?');
    on.meta?.({
      message_id: 'm1',
      intent: question ? 'explain' : 'change',
      handoff: question ? null : 'studio',
    });
    if (!question) return null;
    on.delta?.('It got 9.7× more. ');
    on.reset?.(); // the planted sentence was held back
    on.delta?.('Your reels with a choice-question ending got 1.66× your usual comments. ');
    return {
      message_id: 'm2',
      text: 'Your reels with a choice-question ending got 1.66× your usual comments.',
      sources: [{ kind: 'pattern', id: 'c1', title: 'A choice-question ending' }],
      checked: 'model_retry',
      jobs: [],
    };
  },
}));

const initial = useApp.getState();
const s = () => useApp.getState();

// Toasts clear themselves after a few seconds: fake timers, so no timer outlives the tests.
beforeEach(() => {
  jest.useFakeTimers();
  mockCalls.length = 0;
  mockProjects.clear();
  mockSims.clear();
  useApp.setState(initial, true);
});

afterEach(() => {
  jest.clearAllTimers();
  jest.useRealTimers();
});

async function openGanpati() {
  await s().openInStudio('o1', 'Ganpati dress ideas');
}

describe('navigation', () => {
  it('re-tapping Home returns to the Home root and closes Saved', () => {
    s().openInsights(2);
    s().openSaved();
    s().nav('home');
    expect(s().homeView).toBe('home');
    expect(s().overlay).toBeNull();
  });

  it('Open in Studio starts a project from the opportunity', async () => {
    await openGanpati();
    expect(s().tab).toBe('studio');
    expect(mockCalls[0]).toEqual({ fn: 'startProject', args: [{ opportunity_id: 'o1' }] });
    expect(s().studio.projectId).toBe('p1');
    expect(s().studio.busy).toBeNull();
  });
});

describe('Ask Curo', () => {
  it('answers a question in the step’s thread, with what was held back cleared', async () => {
    await openGanpati();
    await s().askCuro('Why this hook?');
    const thread = s().chat['studio:p1:ideas'];
    expect(thread.map((m) => m.role)).toEqual(['user', 'curo']);
    expect(thread[1].text).toBe(
      'Your reels with a choice-question ending got 1.66× your usual comments.',
    );
    expect(thread[1].text).not.toContain('9.7');
    expect(thread[1].sources?.[0].kind).toBe('pattern');
    expect(thread[1].pending).toBe(false);
    expect(s().asking).toBeNull();
  });

  it('sends nothing where there is no chat box', async () => {
    await s().askCuro('Why?'); // Home
    expect(mockCalls.filter((c) => c.fn === 'sendChat')).toHaveLength(0);
  });
});

describe('composer routing', () => {
  it('shows the right composer per screen and none on Home', async () => {
    expect(composerFor(s())).toBeNull();
    s().nav('studio');
    expect(composerFor(s())?.key).toBe('validate');
    await openGanpati();
    expect(composerFor(s())?.key).toBe('ideas');
  });

  it('validates a typed idea, then develops it into a project', async () => {
    s().nav('studio');
    await s().askCuro('A festive outfit reel'); // handed back to the validate step
    expect(mockCalls[0]).toEqual({
      fn: 'sendChat',
      args: [
        {
          message: 'A festive outfit reel',
          screen: 'studio:validate',
          project_id: null,
          simulation_id: null,
          frame_id: null,
        },
      ],
    });
    expect(s().chat['studio:validate']).toEqual([]); // the step shows the message itself
    const turn = s().studio.validations[0];
    expect(turn.result?.verdict).toBe('Worth trying');
    await s().developValidated(turn);
    expect(mockCalls.at(-1)).toEqual({
      fn: 'startProject',
      args: [{ idea_text: 'A festive outfit reel' }],
    });
    expect(s().studio.stage).toBe('idea');
    expect(s().studio.ideaTitle).toBe('A festive outfit reel');
  });
});

describe('script requests', () => {
  it('tells a pasted script from a request', () => {
    expect(looksLikeScript('Make the hook stronger')).toBe(false);
    expect(looksLikeScript('One outfit, three looks.\nLook one: belted.')).toBe(true);
  });

  it('keeps a pasted script as written and revises on a request', async () => {
    await openGanpati();
    mockProjects.set(
      'p1',
      mockProject({
        idea: mockIdea as Project['idea'],
        script: { version: 1 } as Project['script'],
      }),
    );
    await s().scriptSend('One outfit, three looks.\nLook one: belted.\nWhich one?');
    expect(mockCalls.at(-1)?.fn).toBe('ownScript');
    await s().scriptSend('Make the hook stronger');
    expect(mockCalls.at(-1)).toEqual({
      fn: 'reviseScript',
      args: ['p1', 'Make the hook stronger'],
    });
  });

  it('shows why a step failed and stops showing it as busy', async () => {
    await openGanpati();
    const api = jest.requireMock('@/api/studio');
    jest.spyOn(api, 'writeScript').mockRejectedValueOnce(new Error('Pick an idea first.'));
    await s().generateScript(null);
    expect(s().toast?.text).toBe('Pick an idea first.');
    expect(s().studio.busy).toBeNull();
  });
});

describe('hashtags', () => {
  it('refuses a sixth (the API and database refuse it too)', async () => {
    await openGanpati();
    const five = ['ganpati', 'ganpatioutfit', 'festivelook', 'ethnicstyling', 'mumbaistyle'];
    mockProjects.set(
      'p1',
      mockProject({ captions: { hashtags: five } as unknown as Project['captions'] }),
    );
    await s().toggleTag('outfitideas');
    expect(mockCalls.some((c) => c.fn === 'putHashtags')).toBe(false);
    expect(s().toast?.text).toMatch(/up to 5 hashtags/);
    await s().toggleTag('mumbaistyle'); // remove one…
    await s().toggleTag('outfitideas'); // …then the sixth fits
    expect(mockCalls.at(-1)?.args[1]).toEqual([...five.slice(0, 4), 'outfitideas']);
  });
});

describe('drafts', () => {
  it('asks for an idea before saving, then saves from the current step', async () => {
    await openGanpati();
    await s().saveDraft();
    expect(s().toast?.text).toMatch(/Pick an idea first/);
    mockProjects.set('p1', mockProject({ idea: mockIdea as Project['idea'] }));
    useApp.setState({ studio: { ...s().studio, stage: 'final' } });
    await s().saveDraft();
    expect(mockCalls.at(-1)).toEqual({ fn: 'saveDraft', args: ['p1', 'final'] });
  });
});

describe('simulator', () => {
  const calls = (fn: string) => mockCalls.filter((c) => c.fn === fn);

  async function linkedDraft() {
    mockProjects.set('p1', mockProject({ idea: mockIdea as Project['idea'] }));
    useApp.setState({
      studio: { ...s().studio, projectId: 'p1', ideaTitle: mockIdea.text },
      tab: 'sim',
    });
  }

  it('a sample take runs a simulation linked to the Studio draft and shows its result', async () => {
    await linkedDraft();
    await s().uploadSample('take1', 'First take');
    expect(s().sim.upload).toMatchObject({ name: 'First take', durationS: 41 });
    await s().runSim();
    expect(calls('runSimulation')[0].args[0]).toEqual({
      upload_path: 'uploads/c1/take1.mp4',
      project_id: 'p1',
      audience: 'both',
      // The draft has no chosen caption yet, so the sample's own caption goes with it.
      caption: 'Same outfit, three looks for Ganpati #ganpatioutfit',
    });
    expect(s().sim.view).toBe('result');
    expect(s().sim.simulationId).toBe('s1');
  });

  it('the linked draft’s chosen caption is used instead of the sample’s', async () => {
    await linkedDraft();
    mockProjects.set(
      'p1',
      mockProject({
        idea: mockIdea as Project['idea'],
        captions: { chosen: 0 } as Project['captions'],
      }),
    );
    await s().uploadSample('take1', 'First take');
    await s().runSim();
    expect((calls('runSimulation')[0].args[0] as { caption: unknown }).caption).toBeNull();
  });

  it('a failed simulation goes back to the upload with its reason', async () => {
    useApp.setState({
      sim: {
        ...freshSim(),
        upload: {
          path: 'uploads/c1/broken.mp4',
          name: 'x',
          durationS: 95,
          width: null,
          height: null,
          caption: null,
        },
      },
    });
    await s().runSim();
    expect(s().sim.view).toBe('intro');
    expect(s().toast?.text).toMatch(/95 seconds long/);
  });

  it('a video over 90 seconds is refused before it is uploaded', async () => {
    await s().uploadPicked({
      uri: 'file:///long.mov',
      name: 'long.mov',
      mimeType: 'video/quicktime',
      durationS: 95,
      width: 1080,
      height: 1920,
    });
    expect(calls('uploadVideo')).toHaveLength(0);
    expect(s().toast?.text).toMatch(/95 seconds long/);
  });

  it('Edit & re-run writes the picked edits one at a time, then waits for the new take', async () => {
    await linkedDraft();
    await s().uploadSample('take1', 'First take');
    await s().runSim();
    s().toggleEdit('e1');
    s().toggleEdit('e2');
    s().toggleEdit('e2'); // changed their mind
    await s().editRerun();
    expect(calls('applyEdit').map((c) => c.args)).toEqual([['s1', 'e1', 'p1']]);
    expect(s().sim.pending).toEqual({});
    expect(s().sim.awaitingTake).toBe(true);
    expect(s().toast?.text).toMatch(/written to your Studio script/);
  });

  it('the re-recorded take re-runs against the result on screen', async () => {
    await linkedDraft();
    await s().uploadSample('take1', 'First take');
    await s().runSim();
    await s().rerunSample('take2', 'Re-recorded');
    expect(calls('rerun')[0].args[0]).toBe('s1');
    expect(s().sim.view).toBe('result');
    expect(s().sim.simulationId).toBe('s2');
    expect(s().sim.upload?.name).toBe('Re-recorded');
  });

  it('the audience toggle only switches what is shown', async () => {
    await linkedDraft();
    await s().uploadSample('take1', 'First take');
    await s().runSim();
    s().setAudience('new');
    expect(s().sim.audience).toBe('new');
    expect(calls('runSimulation')).toHaveLength(1);
  });
});
