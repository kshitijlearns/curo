'use client';
/**
 * Studio (v3 look): from an opportunity (or the creator's own idea) to ideas, a script (a
 * timeline of coloured beats), a storyboard (a row of 9:16 frames) and a caption with at most
 * five hashtags. Every step runs as a job; Ask Curo (the Composer)
 * changes any step in plain words. A project credit includes up to 10 revisions.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';

import { AskThread, useAskCuro } from '@/components/AskCuro';
import { Arrow, Chip, ErrorNote, Loading, TopBar } from '@/components/Chrome';
import { Icon, type IconName } from '@/components/Icon';
import { SectionHead, WhoThisIsFor } from '@/components/Personas';
import { api, waitForJob, type S } from '@/lib/api';
import { useOpportunities, usePersonaReactions, useProject, useSaved } from '@/lib/hooks';
import { blockAt, scoreBlock } from '@/lib/palette';
import { useApp } from '@/state/app';

const MAX_HASHTAGS = 5;
type Step = 'ideas' | 'script' | 'storyboard' | 'caption';
const STEPS: { id: Step; label: string }[] = [
  { id: 'ideas', label: 'Ideas' },
  { id: 'script', label: 'Script' },
  { id: 'storyboard', label: 'Storyboard' },
  { id: 'caption', label: 'Caption' },
];
const STEP_ICON: Record<Step, IconName> = { ideas: 'bolt', script: 'lines', storyboard: 'grid', caption: 'hash' };
const STEP_BLOCK: Record<Step, string> = { ideas: 'violet', script: 'lemon', storyboard: 'sky', caption: 'lime' };

export function StudioView() {
  const s = useApp();
  return s.projectId ? <ProjectView id={s.projectId} /> : <StudioStart />;
}

// ---------------------------------------------------------------------- start

function StudioStart() {
  const s = useApp();
  const saved = useSaved();
  const opps = useOpportunities();
  const qc = useQueryClient();
  const [idea, setIdea] = useState('');
  const check = useMutation({
    mutationFn: (text: string) => api<S['Validation']>('/ideas/validate', { body: { text } }),
  });
  const make = useMutation({
    mutationFn: (text: string) => api<S['ProjectStarted']>('/projects', { body: { idea_text: text } }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['me'] });
      s.openProject(r.project_id);
    },
  });

  useEffect(() => {
    s.setComposer({
      placeholder: 'Type an idea to check it',
      busy: check.isPending,
      onSend: (t) => {
        setIdea(t);
        check.mutate(t);
      },
    });
    return () => s.setComposer(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [check.isPending]);

  const v = check.data;
  // The persona row shows the validated idea's reactions (computed with the verdict).
  useEffect(() => {
    s.setPersonaTarget(v?.personas ? { projectId: null, key: `validate:${v.text}`, reactions: v.personas } : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [v]);
  useEffect(() => () => s.setPersonaTarget(null), []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      <TopBar />
      <div className="hero">
        <span className="eyebrow">Studio</span>
        <h1 className="display-title">
          What are we
          <br />
          <span className="hl lemon">making</span> today?
        </h1>
      </div>

      <ol className="flow" aria-label="How Studio works">
        {STEPS.map((st, i) => (
          <li key={st.id} className={`blk-${STEP_BLOCK[st.id]}`}>
            <Icon name={STEP_ICON[st.id]} size={18} strokeWidth={2} />
            <span>{st.label}</span>
            {i < STEPS.length - 1 ? <i aria-hidden="true" /> : null}
          </li>
        ))}
      </ol>
      <p className="hint-line">
        <Icon name="comments" size={16} strokeWidth={2} /> Type an idea below and Curo scores it with your followers.
      </p>

      {check.isPending ? <Loading text="Scoring your idea…" /> : null}
      {check.error ? <ErrorNote error={check.error} /> : null}
      {v ? (
        <section className={`verdict blk-${scoreBlock(v.score)}`} aria-label="Your idea’s score">
          <div className="row between" style={{ alignItems: 'flex-start' }}>
            <Chip>{v.verdict}</Chip>
            <span className="verdict-score" aria-label={`Score ${Math.round(v.score * 100)} of 100`}>
              {Math.round(v.score * 100)}
            </span>
          </div>
          <h3 className="block-title" style={{ fontSize: 24 }}>
            {idea}
          </h3>
          {v.personas?.summary ? <p className="small" style={{ margin: '0 0 10px', fontWeight: 600 }}>{v.personas.summary}</p> : null}
          <div className="stack" style={{ gap: 6 }}>
            {v.reasons.map((r) => (
              <div key={r.text} className="pill-row static">
                <span className="pill-row-main">
                  <strong className="wrap-text">{r.text}</strong>
                  <small className="wrap-text">{r.evidence}</small>
                </span>
              </div>
            ))}
            {v.tweaks.map((t) => (
              <div key={t.text} className="pill-row static">
                <span className="circle sm cream" aria-hidden="true">
                  <Icon name="bolt" size={14} strokeWidth={2} />
                </span>
                <span className="pill-row-main">
                  <strong className="wrap-text">{t.text}</strong>
                </span>
              </div>
            ))}
          </div>
          <button className="btn block ink" style={{ marginTop: 14 }} onClick={() => make.mutate(idea)} disabled={make.isPending}>
            <Icon name="sparkle" size={16} /> Make this
          </button>
        </section>
      ) : null}

      {opps.data?.length ? (
        <>
          <SectionHead
            title="Start from an opportunity"
            action={
              <button className="see-all" onClick={() => s.nav('home')}>
                All
              </button>
            }
          />
          <div className="mini-deck">
            {opps.data.slice(0, 3).map((o, i) => (
              <button
                key={o.id}
                className={`mini-card blk-${blockAt(i)}`}
                onClick={() => {
                  s.openOpp(o.id);
                  s.nav('home');
                }}
              >
                <span className="mini-score">{o.score_shown}</span>
                <span className="pill-row-main">
                  <small>{o.tag}</small>
                  <strong>{o.name}</strong>
                </span>
                <Arrow />
              </button>
            ))}
          </div>
        </>
      ) : null}

      {saved.data?.drafts?.length ? (
        <>
          <SectionHead title="Your drafts" />
          <div className="panel-block lemon">
            {(saved.data.drafts ?? []).map((d) => (
              <button key={d.id} className="pill-row" onClick={() => s.openProject(d.id)}>
                <span className="circle sm cream" aria-hidden="true">
                  <Icon name="film" size={16} strokeWidth={2} />
                </span>
                <span className="pill-row-main">
                  <strong>{d.title}</strong>
                  {d.opportunity ? <small>{d.opportunity}</small> : null}
                </span>
                <Icon name="chevronRight" size={18} strokeWidth={2} />
              </button>
            ))}
          </div>
        </>
      ) : null}
    </>
  );
}

// ---------------------------------------------------------------------- a project

function ProjectView({ id }: { id: string }) {
  const s = useApp();
  const qc = useQueryClient();
  const q = useProject(id);
  const [step, setStep] = useState<Step | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ['project', id] });

  const p = q.data;
  const current: Step = step ?? stepOf(p);
  const ask = useAskCuro({ screen: screenOf(current), projectId: id, onJobDone: refresh });
  const [focusIdea, setFocusIdea] = useState<string | null>(null);
  const target = personaTargetOf(p, current, focusIdea);

  // The persona row reacts to what's on screen: the idea in focus, or this step's draft.
  // A new content version is a new key, so reactions re-run once per revision.
  useEffect(() => {
    s.setPersonaTarget(target ? { projectId: id, key: target.key, target: target.body } : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, target?.key]);
  useEffect(() => () => s.setPersonaTarget(null), []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    s.setComposer({
      placeholder: current === 'ideas' ? 'Ask Curo for different ideas' : `Change the ${current} in your words`,
      busy: ask.busy || !!running,
      onSend: (t) => ask.send(t),
    });
    return () => s.setComposer(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current, ask.busy, running, ask.send]);

  /** Start a step's job and wait for it. */
  const run = async (label: string, path: string, body: unknown = {}) => {
    setRunning(label);
    try {
      const job = await api<S['StudioJob']>(`/projects/${id}/${path}`, { body });
      await waitForJob(job.job_id);
      await refresh();
    } catch (e) {
      s.showToast(e instanceof Error ? e.message : 'That didn’t work.');
    } finally {
      setRunning(null);
    }
  };

  if (q.isLoading) return <Loading />;
  if (q.error || !p) return <ErrorNote error={q.error} onRetry={() => q.refetch()} />;

  return (
    <>
      <div className="row between project-top">
        <button className="chip-btn" onClick={() => s.openProject(null)}>
          <Icon name="back" size={16} strokeWidth={2} /> Studio
        </button>
        <button
          className="chip-btn"
          onClick={async () => {
            await api(`/projects/${id}/save`, { body: { step: current } });
            qc.invalidateQueries({ queryKey: ['saved'] });
            qc.invalidateQueries({ queryKey: ['me'] });
            s.showToast('Draft saved. Find it in your account.');
          }}
        >
          <Icon name="bookmark" size={16} strokeWidth={2} /> Save draft
        </button>
      </div>
      <h1 className="display-title project-title">{p.title || p.opportunity?.name || 'Your project'}</h1>
      {p.opportunity ? (
        <span className="chip outline" style={{ marginBottom: 14 }}>
          <Icon name="bookmark" size={13} strokeWidth={2} /> {p.opportunity.name}
        </span>
      ) : null}

      <nav className="steps" aria-label="Studio steps">
        {STEPS.map((st, i) => {
          const idx = STEPS.findIndex((x) => x.id === current);
          const done = i < idx;
          return (
            <button
              key={st.id}
              aria-current={st.id === current ? 'step' : undefined}
              className={done ? 'done' : undefined}
              onClick={() => setStep(st.id)}
              disabled={!reachable(p, st.id)}
            >
              <span className="step-n">{done ? <Icon name="check" size={14} strokeWidth={3} /> : i + 1}</span>
              <Icon name={STEP_ICON[st.id]} size={18} strokeWidth={2} />
              <span className="step-label">{st.label}</span>
            </button>
          );
        })}
      </nav>

      {running ? <Working text={running} /> : null}

      {current === 'ideas' ? (
        <IdeasStep
          p={p}
          busy={!!running}
          focus={target?.body.target_id ?? null}
          onFocus={setFocusIdea}
          onMore={() => run('Writing three new ideas…', 'ideas', { prompt: null })}
          onPick={async (ideaId) => {
            await api(`/projects/${id}/ideas/${ideaId}/select`, { body: {} });
            setStep('script');
            if (!p.script) await run('Writing your script…', 'script', { direction: null, regenerate: false });
            else refresh();
          }}
        />
      ) : null}
      {current === 'script' ? (
        <ScriptStep
          p={p}
          busy={!!running}
          onWrite={() => run('Writing your script…', 'script', { direction: null, regenerate: !!p.script })}
          onOwn={async (text) => {
            await api(`/projects/${id}/script`, { method: 'PUT', body: { text } });
            refresh();
          }}
          onNext={async () => {
            setStep('storyboard');
            if (!p.storyboard || !p.storyboard.up_to_date) await run('Drawing your storyboard…', 'storyboard');
          }}
        />
      ) : null}
      {current === 'storyboard' ? (
        <StoryboardStep
          p={p}
          busy={!!running}
          onDraw={() => run('Drawing your storyboard…', 'storyboard')}
          onNext={async () => {
            setStep('caption');
            if (!p.captions) await run('Writing captions and hashtags…', 'captions');
          }}
        />
      ) : null}
      {current === 'caption' ? (
        <CaptionStep
          p={p}
          busy={!!running}
          onWrite={() => run('Writing captions and hashtags…', 'captions')}
          onChange={refresh}
          personaKey={target?.key ?? null}
        />
      ) : null}

      <AskThread messages={ask.messages} busy={ask.busy} />
    </>
  );
}

/** A step running: three bouncing dots on a dark card. */
function Working({ text }: { text: string }) {
  return (
    <div className="working" role="status">
      <span className="loader light" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      <span>{text}</span>
    </div>
  );
}

/** What the personas react to on this step, with a key that changes with each content version. */
function personaTargetOf(p: S['Project'] | undefined, st: Step, focusIdea: string | null) {
  if (!p) return null;
  if (st === 'ideas') {
    const rounds = (p.rounds ?? []) as S['IdeaRound'][];
    const latest = rounds[rounds.length - 1];
    const ids = (latest?.ideas ?? (p.idea ? [p.idea] : [])).map((i) => i.id);
    const pick = (focusIdea && ids.includes(focusIdea) ? focusIdea : null) ?? p.idea?.id ?? ids[0];
    return pick ? { key: `idea:${pick}`, body: { target_type: 'idea' as const, target_id: pick } } : null;
  }
  if (st === 'script' && p.script) return { key: `script:${p.script.version}`, body: { target_type: 'script' as const } };
  if (st === 'storyboard' && p.storyboard) return { key: `storyboard:${p.storyboard.version}`, body: { target_type: 'storyboard' as const } };
  if (st === 'caption' && p.captions) return { key: `caption:${p.captions.version}`, body: { target_type: 'caption' as const } };
  return null;
}

function stepOf(p?: S['Project']): Step {
  if (!p) return 'ideas';
  if (p.step === 'caption' || p.step === 'final') return 'caption';
  if (p.step === 'storyboard') return 'storyboard';
  if (p.step === 'script' || p.step === 'idea') return p.script ? 'script' : 'ideas';
  return 'ideas';
}

function reachable(p: S['Project'], st: Step) {
  if (st === 'ideas') return true;
  if (st === 'script') return !!p.idea;
  if (st === 'storyboard') return !!p.script;
  return !!p.storyboard;
}

function screenOf(st: Step): S['ChatIn']['screen'] {
  return st === 'ideas' ? 'studio:ideas' : st === 'caption' ? 'studio:caption' : (`studio:${st}` as S['ChatIn']['screen']);
}

// ---------------------------------------------------------------------- steps

const SLOT = { proven: 'Proven for you', adapted: 'A trend, made yours', explore: 'Worth exploring' };
const PART = { H: 'Your history', A: 'Audience', T: 'Trend', N: 'Novelty' } as const;
const PART_BLOCK = { H: 'violet', A: 'pink', T: 'lime', N: 'sky' } as const;
const IDEA_BLOCKS = ['violet', 'lemon', 'coral'] as const;

function IdeasStep({
  p,
  busy,
  focus,
  onFocus,
  onMore,
  onPick,
}: {
  p: S['Project'];
  busy: boolean;
  focus: string | null;
  onFocus: (id: string) => void;
  onMore: () => void;
  onPick: (id: string) => void;
}) {
  const rounds = p.rounds as S['IdeaRound'][];
  const latest = rounds[rounds.length - 1];
  // A project from the creator's own idea (or a persona's "Make this") starts with that idea.
  const shown = latest?.ideas ?? (p.idea ? [p.idea] : []);
  if (!shown.length) return busy ? null : <Working text="Curo is writing your first three ideas…" />;
  return (
    <>
      {shown.map((idea, i) => (
        <article key={idea.id} className={`idea-card blk-${IDEA_BLOCKS[i % 3]}${idea.selected ? ' picked' : ''}`} style={{ animationDelay: `${i * 70}ms` }}>
          <div className="row between" style={{ alignItems: 'flex-start' }}>
            <Chip>
              {idea.selected ? <Icon name="check" size={13} strokeWidth={3} /> : null}
              {idea.slot ? SLOT[idea.slot] : 'Your idea'}
            </Chip>
            {idea.score !== null && idea.score !== undefined ? (
              <span className="idea-score" aria-label={`Idea score ${Math.round(idea.score * 100)} of 100`}>
                {Math.round(idea.score * 100)}
              </span>
            ) : null}
          </div>
          <h3 className="idea-title">{idea.text}</h3>
          <p className="idea-desc">{idea.description}</p>
          {idea.why ? (
            <p className="idea-why">
              <Icon name="trend" size={14} strokeWidth={2.2} /> {idea.why}
            </p>
          ) : null}
          {idea.shares ? (
            <div className="idea-mix">
              <div className="split-bar thin" aria-hidden="true">
                {(Object.keys(PART) as (keyof typeof PART)[]).map((k) => (
                  <i key={k} className={`blk-${PART_BLOCK[k]}`} style={{ flex: idea.shares![k] || 0.01 }} />
                ))}
              </div>
              <div className="row wrap" style={{ gap: 10, marginTop: 6 }}>
                {(Object.keys(PART) as (keyof typeof PART)[]).map((k) => (
                  <span key={k} className="legend">
                    <i className={`blk-${PART_BLOCK[k]}`} /> {PART[k]} {idea.shares![k]}%
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          <div className="row" style={{ marginTop: 14, gap: 8 }}>
            <button className="btn ink" style={{ flex: 1 }} onClick={() => onPick(idea.id)} disabled={busy}>
              {idea.selected ? 'Continue with this' : 'Make this one'} <Icon name="arrowRight" size={16} strokeWidth={2} />
            </button>
            <button className={`btn small ${focus === idea.id ? 'white' : 'clear'}`} onClick={() => onFocus(idea.id)} aria-pressed={focus === idea.id}>
              <Icon name="users" size={16} strokeWidth={2} /> {focus === idea.id ? 'Reacting below' : 'Reactions'}
            </button>
          </div>
        </article>
      ))}
      <button className="btn block ghost" onClick={onMore} disabled={busy}>
        <Icon name="refresh" size={18} strokeWidth={2} /> Three different ideas
      </button>
    </>
  );
}

const ROLE_BLOCK: Record<string, string> = { hook: 'coral', setup: 'lemon', item: 'sky', ending: 'lime', payoff: 'lime', cta: 'pink' };

function ScriptStep({
  p,
  busy,
  onWrite,
  onOwn,
  onNext,
}: {
  p: S['Project'];
  busy: boolean;
  onWrite: () => void;
  onOwn: (text: string) => void;
  onNext: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState('');
  const sc = p.script;
  if (!sc) {
    return (
      <button className="btn block ink big" onClick={onWrite} disabled={busy}>
        <Icon name="lines" size={18} strokeWidth={2} /> Write the script
      </button>
    );
  }
  const changed = sc.version > 1 ? (sc.changed_beat_ids ?? []) : [];
  return (
    <>
      <div className="row wrap" style={{ gap: 6, marginBottom: 12 }}>
        <span className="chip ink">
          <Icon name="clock" size={14} strokeWidth={2} /> {Math.round(sc.seconds)}s
        </span>
        <span className="chip outline">{sc.words} words</span>
        {sc.band ? <span className="chip outline">Best: {sc.band.split(',')[0]}</span> : null}
      </div>
      {sc.reply ? (
        <div className="note-card">
          <span className="circle sm white" aria-hidden="true">
            <Icon name="sparkle" size={14} />
          </span>
          <p>{sc.reply}</p>
        </div>
      ) : null}
      {editing ? (
        <>
          <textarea className="field" value={text} onChange={(e) => setText(e.target.value)} aria-label="Your script" rows={10} />
          <div className="row" style={{ marginTop: 10 }}>
            <button className="btn ink" onClick={() => (onOwn(text), setEditing(false))} disabled={!text.trim()}>
              Use my script
            </button>
            <button className="btn ghost" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </>
      ) : (
        <ol className="timeline" aria-label="Script beats">
          {sc.beats.map((b) => (
            <li key={b.id}>
              <span className="tl-time">{b.t.split('–')[0].trim()}</span>
              <div className={`tl-card blk-${ROLE_BLOCK[b.role] ?? 'pink'}`}>
                <div className="row between">
                  <span className="tl-role">{b.role}</span>
                  {changed.includes(b.id) ? <span className="chip white">Changed</span> : <span className="tl-range">{b.t}</span>}
                </div>
                <p className="tl-text">{b.text}</p>
                {b.note ? (
                  <p className="tl-note">
                    <Icon name="bolt" size={13} strokeWidth={2} filled /> {(b.note as { title?: string; text?: string }).title ?? (b.note as { text?: string }).text}
                  </p>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      )}
      {!editing ? (
        <div className="stack">
          <button className="btn block ink big" onClick={onNext} disabled={busy}>
            Next: storyboard <Icon name="arrowRight" size={18} strokeWidth={2} />
          </button>
          <div className="row">
            <button className="btn ghost small" style={{ flex: 1 }} onClick={onWrite} disabled={busy}>
              <Icon name="refresh" size={16} strokeWidth={2} /> Write it again
            </button>
            <button
              className="btn ghost small"
              style={{ flex: 1 }}
              onClick={() => {
                setText(sc.beats.map((b) => b.text).join('\n'));
                setEditing(true);
              }}
            >
              <Icon name="lines" size={16} strokeWidth={2} /> My own words
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}

const FRAME_BLOCKS = ['coral', 'lemon', 'sky', 'lime', 'pink', 'violet'] as const;

function StoryboardStep({
  p,
  busy,
  onDraw,
  onNext,
}: {
  p: S['Project'];
  busy: boolean;
  onDraw: () => void;
  onNext: () => void;
}) {
  const sb = p.storyboard;
  if (!sb) {
    return (
      <button className="btn block ink big" onClick={onDraw} disabled={busy}>
        <Icon name="grid" size={18} strokeWidth={2} /> Draw the storyboard
      </button>
    );
  }
  return (
    <>
      <div className="feas">
        <span className="feas-score">{sb.feasibility.label}</span>
        <span className="feas-main">
          <strong>to shoot · {sb.frames.length} frames</strong>
          <small>{sb.feasibility.detail}</small>
        </span>
      </div>
      {!sb.up_to_date ? (
        <div className="banner blk-lemon">
          <span className="banner-main">
            <strong>The script changed</strong>
            <small>Redraw to match it.</small>
          </span>
          <button className="btn small ink" onClick={onDraw} disabled={busy}>
            Redraw
          </button>
        </div>
      ) : null}
      <div className="frames" role="list" aria-label="Storyboard frames">
        {sb.frames.map((f, i) => (
          <article key={f.id} role="listitem" className={`frame blk-${FRAME_BLOCKS[i % FRAME_BLOCKS.length]}`} style={{ opacity: f.stale ? 0.55 : 1 }}>
            <div className="row between">
              <span className="frame-n">{i + 1}</span>
              <span className="chip white">{f.t.split('–')[0].trim()}</span>
            </div>
            <span className="frame-shot">{f.shot_type.replaceAll('_', ' ')}</span>
            <p className="frame-do">{f.instruction}</p>
            {f.onscreen_text ? <span className="frame-text">“{f.onscreen_text}”</span> : null}
            <p className="frame-says">
              <Icon name="mic" size={13} strokeWidth={2} /> {f.line}
            </p>
            {f.transition ? <span className="frame-cut">{f.transition} →</span> : null}
          </article>
        ))}
      </div>
      <button className="btn block ink big" onClick={onNext} disabled={busy}>
        Next: caption <Icon name="arrowRight" size={18} strokeWidth={2} />
      </button>
    </>
  );
}

const JOB_ICON = { comments: 'comments', likes: 'likes', shares: 'shares', saves: 'bookmark' } as const;

function CaptionStep({
  p,
  busy,
  onWrite,
  onChange,
  personaKey,
}: {
  p: S['Project'];
  busy: boolean;
  onWrite: () => void;
  onChange: () => void;
  personaKey: string | null;
}) {
  const s = useApp();
  const who = usePersonaReactions(p.id, personaKey, { target_type: 'caption' });
  const c = p.captions;
  const [tags, setTags] = useState<string[]>(c?.hashtags ?? []);
  useEffect(() => setTags(c?.hashtags ?? []), [c?.hashtags]);
  const candidates = useMemo(() => c?.candidates ?? [], [c]);
  if (!c) {
    return (
      <button className="btn block ink big" onClick={onWrite} disabled={busy}>
        <Icon name="hash" size={18} strokeWidth={2} /> Write captions and hashtags
      </button>
    );
  }
  const toggle = async (tag: string) => {
    const next = tags.includes(tag) ? tags.filter((t) => t !== tag) : [...tags, tag];
    if (next.length > MAX_HASHTAGS) {
      s.showToast('Instagram allows five hashtags. Remove one first.');
      return;
    }
    setTags(next);
    try {
      await api(`/projects/${p.id}/hashtags`, { method: 'PUT', body: { hashtags: next } });
      onChange();
    } catch (e) {
      s.showToast(e instanceof Error ? e.message : 'Couldn’t save the hashtags.');
    }
  };
  return (
    <>
      <h2 className="section-label">Pick a caption</h2>
      {c.options.map((o, i) => {
        const on = c.chosen === i;
        return (
          <button
            key={i}
            className={`caption-card${on ? ' on' : ''}`}
            onClick={async () => {
              await api(`/projects/${p.id}/caption`, { method: 'PUT', body: { chosen: i } });
              onChange();
            }}
            aria-pressed={on}
          >
            <div className="row between">
              <span className="chip ink">
                <Icon name={JOB_ICON[o.job as keyof typeof JOB_ICON] ?? 'sparkle'} size={13} strokeWidth={2} /> For {o.job}
              </span>
              <span className={`radio${on ? ' on' : ''}`} aria-hidden="true">
                {on ? <Icon name="check" size={14} strokeWidth={3} /> : null}
              </span>
            </div>
            <p className="caption-text">{o.text}</p>
            <p className="caption-why">{o.why}</p>
          </button>
        );
      })}
      <div className="section-head" style={{ marginTop: 22 }}>
        <h2>Hashtags</h2>
        <span className="tag-count" aria-label={`${tags.length} of ${MAX_HASHTAGS} hashtags`}>
          {Array.from({ length: MAX_HASHTAGS }, (_, i) => (
            <i key={i} className={i < tags.length ? 'on' : ''} />
          ))}
          <b>
            {tags.length}/{MAX_HASHTAGS}
          </b>
        </span>
      </div>
      <div className="row wrap" style={{ gap: 8, marginBottom: 18 }}>
        {[...new Set([...tags, ...candidates.map((h) => h.tag)])].map((tag) => {
          const on = tags.includes(tag);
          const kind = candidates.find((h) => h.tag === tag)?.kind;
          return (
            <button key={tag} className={`tag${on ? ' on' : ''}`} aria-pressed={on} onClick={() => toggle(tag)}>
              #{tag}
              {kind && !on ? <small>{kind}</small> : null}
            </button>
          );
        })}
      </div>
      <section className="ready-card">
        <span className="eyebrow" style={{ color: 'var(--lime)' }}>
          All set
        </span>
        <h3 className="block-title" style={{ color: 'var(--white)' }}>
          Ready to record
        </h3>
        <p>Record it, then test it on your AI audience before you post.</p>
        <WhoThisIsFor data={who.data} />
        <button className="btn block coral big" style={{ marginTop: 14 }} onClick={() => s.nav('sim')}>
          <Icon name="simulator" size={18} strokeWidth={2} /> Test it in the Simulator
        </button>
      </section>
    </>
  );
}
