'use client';
/**
 * Studio: from an opportunity (or the creator's own idea) to ideas, a script, a storyboard and
 * a caption with at most five hashtags. Every step runs as a job; Ask Curo (the Composer)
 * changes any step in plain words. A project credit includes up to 10 revisions.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';

import { AskThread, useAskCuro } from '@/components/AskCuro';
import { ErrorNote, Loading } from '@/components/Chrome';
import { Icon } from '@/components/Icon';
import { api, waitForJob, type S } from '@/lib/api';
import { useProject, useSaved } from '@/lib/hooks';
import { useApp } from '@/state/app';

const MAX_HASHTAGS = 5;
type Step = 'ideas' | 'script' | 'storyboard' | 'caption';
const STEPS: { id: Step; label: string }[] = [
  { id: 'ideas', label: 'Ideas' },
  { id: 'script', label: 'Script' },
  { id: 'storyboard', label: 'Storyboard' },
  { id: 'caption', label: 'Caption' },
];

export function StudioView() {
  const s = useApp();
  return s.projectId ? <ProjectView id={s.projectId} /> : <StudioStart />;
}

// ---------------------------------------------------------------------- start

function StudioStart() {
  const s = useApp();
  const saved = useSaved();
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
      hint: 'Curo scores it against your reels, your audience and what’s rising.',
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
  return (
    <>
      <h2 className="section-title">Studio</h2>
      <p className="section-sub">Start from an opportunity area on Home, or check an idea of your own below.</p>
      <button className="btn block lav" onClick={() => s.nav('home')}>
        <Icon name="home" size={18} /> Pick an opportunity area
      </button>

      {check.isPending ? <Loading text="Scoring your idea…" /> : null}
      {check.error ? <ErrorNote error={check.error} /> : null}
      {v ? (
        <div className="card lav" style={{ marginTop: 16 }}>
          <div className="row between">
            <span className="pill white">{v.verdict}</span>
            <span className="score" style={{ fontSize: 28 }}>
              {Math.round(v.score * 100)}
            </span>
          </div>
          <h3 style={{ marginTop: 10 }}>{idea}</h3>
          {v.reasons.map((r) => (
            <p key={r.text} style={{ marginTop: 8 }}>
              {r.text} <span className="small muted">{r.evidence}</span>
            </p>
          ))}
          {v.tweaks.length ? (
            <>
              <p className="small" style={{ fontWeight: 600, marginTop: 12 }}>
                Make it stronger
              </p>
              {v.tweaks.map((t) => (
                <p key={t.text} className="small light">
                  {t.text}
                </p>
              ))}
            </>
          ) : null}
          <button className="btn block" style={{ marginTop: 14 }} onClick={() => make.mutate(idea)} disabled={make.isPending}>
            Make this
          </button>
        </div>
      ) : null}

      {saved.data?.drafts?.length ? (
        <>
          <h2 className="section-title" style={{ marginTop: 24 }}>
            Your drafts
          </h2>
          {(saved.data.drafts ?? []).map((d) => (
            <button key={d.id} className="card tap" onClick={() => s.openProject(d.id)}>
              <div className="row between">
                <h3 style={{ margin: 0 }}>{d.title}</h3>
                <Icon name="chevronRight" />
              </div>
            </button>
          ))}
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

  useEffect(() => {
    s.setComposer({
      placeholder: current === 'ideas' ? 'Ask for different ideas, or ask Curo anything' : `Change the ${current} in your words`,
      hint: 'Ask Curo can change this step for you. Tap the mic to speak.',
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
      <div className="row between" style={{ marginBottom: 12 }}>
        <button className="pill" onClick={() => s.openProject(null)}>
          <Icon name="back" size={16} /> Studio
        </button>
        <button
          className="pill lav"
          onClick={async () => {
            await api(`/projects/${id}/save`, { body: { step: current } });
            qc.invalidateQueries({ queryKey: ['saved'] });
            qc.invalidateQueries({ queryKey: ['me'] });
            s.showToast('Draft saved. Find it under Saved.');
          }}
        >
          <Icon name="bookmark" size={16} /> Save draft
        </button>
      </div>
      <h2 className="section-title" style={{ marginTop: 0 }}>
        {p.title || p.opportunity?.name || 'Your project'}
      </h2>
      {p.opportunity ? <p className="section-sub">From “{p.opportunity.name}”</p> : null}

      <nav className="steps" aria-label="Studio steps">
        {STEPS.map((st) => (
          <button
            key={st.id}
            aria-current={st.id === current ? 'step' : undefined}
            onClick={() => setStep(st.id)}
            disabled={!reachable(p, st.id)}
          >
            {st.label}
          </button>
        ))}
      </nav>

      {running ? <Loading text={running} /> : null}

      {current === 'ideas' ? (
        <IdeasStep
          p={p}
          busy={!!running}
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
        />
      ) : null}

      <AskThread messages={ask.messages} busy={ask.busy} />
    </>
  );
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

function IdeasStep({
  p,
  busy,
  onMore,
  onPick,
}: {
  p: S['Project'];
  busy: boolean;
  onMore: () => void;
  onPick: (id: string) => void;
}) {
  const rounds = p.rounds as S['IdeaRound'][];
  const latest = rounds[rounds.length - 1];
  if (!latest) return busy ? null : <Loading text="Curo is writing your first three ideas…" />;
  return (
    <>
      {latest.ideas.map((idea, i) => (
        <article key={idea.id} className={`card ${idea.selected ? 'lav' : ''}`} style={{ animationDelay: `${i * 70}ms` }}>
          <div className="row between">
            <span className="pill pink">{idea.slot ? SLOT[idea.slot] : 'Your idea'}</span>
            {idea.score !== null && idea.score !== undefined ? (
              <span className="score" style={{ fontSize: 24 }}>
                {Math.round(idea.score * 100)}
              </span>
            ) : null}
          </div>
          <h3 style={{ marginTop: 10 }}>{idea.text}</h3>
          <p className="light">{idea.description}</p>
          <p className="small" style={{ marginTop: 8 }}>
            {idea.why}
          </p>
          {idea.shares ? (
            <div className="row wrap" style={{ marginTop: 10, gap: 6 }}>
              {(Object.keys(PART) as (keyof typeof PART)[]).map((k) => (
                <span key={k} className="pill" style={{ fontWeight: 400 }}>
                  {PART[k]} {idea.shares![k]}%
                </span>
              ))}
            </div>
          ) : null}
          <button className="btn block" style={{ marginTop: 14 }} onClick={() => onPick(idea.id)} disabled={busy}>
            {idea.selected ? 'Continue with this' : 'Make this one'}
          </button>
        </article>
      ))}
      <button className="btn block ghost" onClick={onMore} disabled={busy}>
        <Icon name="refresh" size={18} /> Three different ideas
      </button>
    </>
  );
}

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
      <button className="btn block" onClick={onWrite} disabled={busy}>
        Write the script
      </button>
    );
  }
  return (
    <>
      <div className="row between small muted" style={{ margin: '0 4px 10px' }}>
        <span>
          About {Math.round(sc.seconds)} seconds · {sc.words} words
        </span>
        {sc.band ? <span>{sc.band}</span> : null}
      </div>
      {sc.reply ? <p className="label-sim" style={{ background: 'var(--lavender)' }}>{sc.reply}</p> : null}
      {editing ? (
        <>
          <textarea className="field" value={text} onChange={(e) => setText(e.target.value)} aria-label="Your script" rows={10} />
          <div className="row" style={{ marginTop: 10 }}>
            <button className="btn" onClick={() => (onOwn(text), setEditing(false))} disabled={!text.trim()}>
              Use my script
            </button>
            <button className="btn ghost" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </>
      ) : (
        <div className="card">
          {sc.beats.map((b) => (
            <div key={b.id} style={{ marginBottom: 14, background: (sc.changed_beat_ids ?? []).includes(b.id) ? 'var(--pink)' : undefined, borderRadius: 12, padding: (sc.changed_beat_ids ?? []).includes(b.id) ? 8 : 0 }}>
              <p className="small muted" style={{ fontWeight: 600 }}>
                {b.t} · {b.role}
              </p>
              <p style={{ fontSize: 16 }}>{b.text}</p>
              {b.note ? (
                <p className="small light" style={{ marginTop: 4 }}>
                  {(b.note as { text?: string }).text}
                </p>
              ) : null}
            </div>
          ))}
        </div>
      )}
      {!editing ? (
        <div className="stack">
          <button className="btn block" onClick={onNext} disabled={busy}>
            Next: storyboard <Icon name="arrowRight" size={18} />
          </button>
          <div className="row">
            <button className="btn ghost small" onClick={onWrite} disabled={busy}>
              Write it again
            </button>
            <button
              className="btn ghost small"
              onClick={() => {
                setText(sc.beats.map((b) => b.text).join('\n'));
                setEditing(true);
              }}
            >
              Use my own words
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}

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
      <button className="btn block" onClick={onDraw} disabled={busy}>
        Draw the storyboard
      </button>
    );
  }
  return (
    <>
      <div className="card gray">
        <div className="row between">
          <strong>{sb.feasibility.label} to shoot</strong>
          <span className="small muted">{sb.frames.length} frames</span>
        </div>
        <p className="small light" style={{ marginTop: 6 }}>
          {sb.feasibility.detail}
        </p>
      </div>
      {!sb.up_to_date ? (
        <div className="card pink">
          <p>The script changed since this was drawn.</p>
          <button className="btn small" style={{ marginTop: 10 }} onClick={onDraw} disabled={busy}>
            Redraw
          </button>
        </div>
      ) : null}
      {sb.frames.map((f, i) => (
        <article key={f.id} className="card" style={{ opacity: f.stale ? 0.6 : 1 }}>
          <div className="row" style={{ gap: 12, alignItems: 'flex-start' }}>
            <div
              aria-hidden="true"
              style={{
                width: 64,
                height: 112,
                borderRadius: 12,
                background: 'var(--lavender)',
                flexShrink: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 600,
              }}
            >
              {i + 1}
            </div>
            <div>
              <p className="small muted" style={{ fontWeight: 600 }}>
                {f.t} · {f.shot_type.replaceAll('_', ' ')}
              </p>
              <p style={{ marginTop: 4 }}>{f.instruction}</p>
              {f.onscreen_text ? (
                <p className="small" style={{ marginTop: 6 }}>
                  On screen: “{f.onscreen_text}”
                </p>
              ) : null}
              <p className="small light" style={{ marginTop: 6 }}>
                Says: {f.line}
              </p>
            </div>
          </div>
        </article>
      ))}
      <button className="btn block" onClick={onNext} disabled={busy}>
        Next: caption <Icon name="arrowRight" size={18} />
      </button>
    </>
  );
}

function CaptionStep({
  p,
  busy,
  onWrite,
  onChange,
}: {
  p: S['Project'];
  busy: boolean;
  onWrite: () => void;
  onChange: () => void;
}) {
  const s = useApp();
  const c = p.captions;
  const [tags, setTags] = useState<string[]>(c?.hashtags ?? []);
  useEffect(() => setTags(c?.hashtags ?? []), [c?.hashtags]);
  const candidates = useMemo(() => c?.candidates ?? [], [c]);
  if (!c) {
    return (
      <button className="btn block" onClick={onWrite} disabled={busy}>
        Write captions and hashtags
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
      <h3 className="section-title" style={{ fontSize: 18 }}>
        Pick a caption
      </h3>
      {c.options.map((o, i) => (
        <button
          key={i}
          className={`card tap ${c.chosen === i ? 'lav' : ''}`}
          onClick={async () => {
            await api(`/projects/${p.id}/caption`, { method: 'PUT', body: { chosen: i } });
            onChange();
          }}
          aria-pressed={c.chosen === i}
        >
          <span className="pill white">For {o.job}</span>
          <p style={{ marginTop: 10, whiteSpace: 'pre-wrap' }}>{o.text}</p>
          <p className="small muted" style={{ marginTop: 6 }}>
            {o.why}
          </p>
        </button>
      ))}
      <h3 className="section-title" style={{ fontSize: 18 }}>
        Hashtags · {tags.length} of {MAX_HASHTAGS}
      </h3>
      <div className="row wrap" style={{ gap: 8, marginBottom: 16 }}>
        {[...new Set([...tags, ...candidates.map((h) => h.tag)])].map((tag) => {
          const on = tags.includes(tag);
          const kind = candidates.find((h) => h.tag === tag)?.kind;
          return (
            <button key={tag} className={`pill ${on ? 'blue' : ''}`} aria-pressed={on} onClick={() => toggle(tag)}>
              #{tag}
              {kind && !on ? <span className="small" style={{ fontWeight: 400, opacity: 0.7 }}>{kind}</span> : null}
            </button>
          );
        })}
      </div>
      <div className="card lav">
        <h3>Ready to record</h3>
        <p className="light">Record it, then test it in the Simulator before you post.</p>
        <button className="btn block" style={{ marginTop: 12 }} onClick={() => s.nav('sim')}>
          <Icon name="simulator" size={18} /> Go to the Simulator
        </button>
      </div>
    </>
  );
}
