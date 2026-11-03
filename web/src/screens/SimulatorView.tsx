'use client';
/**
 * The Simulator (v2, v3 look): upload the recorded video; CURO's AI audience — personas built from the
 * creator's own comments — watches it, reacts, comments and replies. The result leads with the
 * engagement score, then predicted ranges, the skip curve, the best time to post, what's
 * working / holding it back / to edit (with timestamps), and the simulated comments, each
 * agent one tap away. Everything the agents say is labelled simulated.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';

import { AskThread, useAskCuro } from '@/components/AskCuro';
import { ErrorNote, Loading, TopBar } from '@/components/Chrome';
import { Overlay } from '@/components/Overlay';
import { Icon, type IconName } from '@/components/Icon';
import { AvatarSkeleton, PersonaAvatar } from '@/components/PersonaAvatar';
import { PersonaChat, PersonaLabel, SectionHead } from '@/components/Personas';
import type { Mood, PersonaColor } from '@/lib/avatar';
import { api, uploadVideo, waitForJob, type S } from '@/lib/api';
import { usePersonas, useProject, useSimulation } from '@/lib/hooks';
import { blockAt, PERSONA_BLOCK, scoreBlock } from '@/lib/palette';
import { useApp } from '@/state/app';

export const SIM_LABEL = 'Simulated by CURO’s AI audience. Not real comments.';

export function SimulatorView() {
  const s = useApp();
  return s.simId ? <SimResult key={s.simId} id={s.simId} /> : <SimStart />;
}

// ---------------------------------------------------------------------- start

function SimStart({ parent }: { parent?: S['Simulation'] }) {
  const s = useApp();
  const qc = useQueryClient();
  const project = useProject(parent ? parent.project_id ?? null : s.projectId);
  const samples = useQuery({ queryKey: ['samples'], queryFn: () => api<S['SampleVideo'][]>('/uploads/samples') });
  const personas = usePersonas();
  const [link, setLink] = useState(true);
  const [caption, setCaption] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const c = project.data?.captions;
    if (!caption && c && c.chosen !== null && c.chosen !== undefined) {
      const tags = c.hashtags.map((h) => `#${h}`).join(' ');
      setCaption(`${c.options[c.chosen]?.text ?? ''}${tags ? `\n\n${tags}` : ''}`);
    }
  }, [project.data, caption]);

  useEffect(() => {
    s.setComposer(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const start = async (path: string, sampleCaption?: string | null) => {
    setBusy('Starting the simulation…');
    try {
      const body = {
        upload_path: path,
        caption: caption || sampleCaption || null,
      };
      const out = parent
        ? await api<S['SimulationStarted']>(`/simulations/${parent.id}/rerun`, { body })
        : await api<S['SimulationStarted']>('/simulations', {
            body: { ...body, audience: 'both', project_id: link && project.data ? project.data.id : null },
          });
      qc.invalidateQueries({ queryKey: ['billing'] });
      s.openSim(out.simulation_id);
    } catch (e) {
      s.showToast(e instanceof Error ? e.message : 'Couldn’t start the simulation.');
    } finally {
      setBusy(null);
    }
  };

  const onFile = async (f: File | undefined) => {
    if (!f) return;
    if (!/^video\/(mp4|quicktime)$/.test(f.type) && !/\.(mp4|mov)$/i.test(f.name)) {
      s.showToast('Upload an MP4 or MOV video.');
      return;
    }
    setBusy('Uploading your video…');
    try {
      const path = await uploadVideo(f);
      await start(path);
    } catch (e) {
      s.showToast(e instanceof Error ? e.message : 'The upload didn’t go through.');
      setBusy(null);
    }
  };

  const pickSample = async (name: string) => {
    setBusy('Getting the sample ready…');
    try {
      const up = await api<S['Uploaded']>('/uploads/sample', { body: { name } });
      await start(up.path, up.caption);
    } catch (e) {
      s.showToast(e instanceof Error ? e.message : 'Couldn’t use that sample.');
      setBusy(null);
    }
  };

  const crowd = (personas.data?.personas ?? []).slice(0, 4);
  return (
    <>
      {parent ? null : <TopBar />}
      <div className="hero">
        <span className="eyebrow">{parent ? 'New take' : 'Simulator'}</span>
        <h1 className="display-title">
          {parent ? (
            <>
              Show them
              <br />
              <span className="hl coral">take two</span>
            </>
          ) : (
            <>
              Test it before
              <br />
              you <span className="hl coral">post</span>
            </>
          )}
        </h1>
      </div>

      <div className="audience-strip">
        <span className="orb-stack" aria-hidden="true">
          {crowd.length
            ? crowd.map((p) => <PersonaAvatar key={p.id} seed={p.avatar_seed} color={p.color as PersonaColor} mood={p.mood as Mood} size={36} decorative animated={false} />)
            : [1, 2, 3, 4].map((i) => <AvatarSkeleton key={i} size={36} seed={i * 4099} />)}
        </span>
        <span className="pill-row-main">
          <strong>1,000 AI followers</strong>
          <small>drawn from your {crowd.length || 4} follower groups</small>
        </span>
      </div>

      {busy ? <Working text={busy} /> : null}

      <input
        ref={file}
        type="file"
        accept="video/mp4,video/quicktime,.mp4,.mov"
        hidden
        onChange={(e) => onFile(e.target.files?.[0])}
      />
      <button className="drop blk-coral" disabled={!!busy} onClick={() => file.current?.click()}>
        <span className="drop-icon">
          <Icon name="upload" size={26} strokeWidth={2.2} />
        </span>
        <strong>Upload your reel</strong>
        <span className="row" style={{ gap: 6, justifyContent: 'center' }}>
          <span className="chip white">MP4 or MOV</span>
          <span className="chip white">up to 90s</span>
        </span>
      </button>

      {project.data && !parent ? (
        <label className="toggle-row">
          <span className="circle sm cream" aria-hidden="true">
            <Icon name="film" size={16} strokeWidth={2} />
          </span>
          <span className="pill-row-main">
            <strong>Link to your draft</strong>
            <small>{project.data.title || project.data.opportunity?.name}</small>
          </span>
          <input type="checkbox" className="switch-input" checked={link} onChange={(e) => setLink(e.target.checked)} />
        </label>
      ) : null}

      <details className="caption-box" open={!!caption}>
        <summary>
          <Icon name="hash" size={16} strokeWidth={2} /> {caption ? 'Your caption' : 'Add the caption you’ll post'}
          <span className="small muted" style={{ marginLeft: 'auto' }}>
            optional
          </span>
        </summary>
        <label htmlFor="caption" className="sr-only">
          Caption (optional)
        </label>
        <textarea
          id="caption"
          className="field"
          value={caption}
          onChange={(e) => setCaption(e.target.value)}
          placeholder="Paste the caption you’ll post"
          rows={3}
          style={{ minHeight: 90 }}
        />
      </details>

      {samples.data?.length ? (
        <>
          <SectionHead title="Or try a sample" />
          <div className="panel-block sky">
            {samples.data.map((v) => (
              <button key={v.name} className="pill-row" disabled={!!busy} onClick={() => pickSample(v.name)}>
                <span className="circle sm ink" aria-hidden="true">
                  <Icon name="play" size={14} />
                </span>
                <span className="pill-row-main">
                  <strong>{v.title}</strong>
                  <small>{v.description.split(' · ').slice(0, -1).join(' · ') || v.description}</small>
                </span>
                <span className="chip cream">{Math.round(v.duration_s)}s</span>
              </button>
            ))}
          </div>
        </>
      ) : null}
    </>
  );
}

// ---------------------------------------------------------------------- result

const STEP_TEXT: Record<string, string> = {
  understanding: 'Watching your video…',
  dna: 'Reading how it’s made…',
  trend: 'Checking it against your reels…',
  compare: 'Comparing with your reels…',
  estimate: 'Estimating…',
  audience: 'Building your AI audience…',
  agents: 'Your AI audience is watching…',
};

function SimResult({ id }: { id: string }) {
  const s = useApp();
  const qc = useQueryClient();
  const q = useSimulation(id);
  const [progress, setProgress] = useState<string>('Starting…');
  const [rerun, setRerun] = useState(false);
  const [agent, setAgent] = useState<number | null>(null);
  const ask = useAskCuro({ screen: 'sim:result', simulationId: id });

  useEffect(() => {
    const jobId = q.data?.job_id;
    if (!jobId || q.data?.status === 'done' || q.data?.status === 'failed') return;
    let stop = false;
    waitForJob(jobId, (p) => !stop && p.step && setProgress(STEP_TEXT[String(p.step)] ?? 'Working…'))
      .catch(() => undefined)
      .finally(() => !stop && qc.invalidateQueries({ queryKey: ['sim', id] }));
    return () => {
      stop = true;
    };
  }, [q.data?.job_id, q.data?.status, id, qc]);

  useEffect(() => {
    if (q.data?.status !== 'done') return s.setComposer(null);
    s.setComposer({
      placeholder: 'Why do people stop at the start?',
      busy: ask.busy,
      onSend: (t) => ask.send(t),
    });
    return () => s.setComposer(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.data?.status, ask.busy, ask.send]);

  if (q.isLoading) return <Loading />;
  if (q.error || !q.data) return <ErrorNote error={q.error} onRetry={() => q.refetch()} />;
  const sim = q.data;
  const top = (
    <div className="row between project-top">
      <button className="chip-btn" onClick={() => s.openSim(null)}>
        <Icon name="back" size={16} strokeWidth={2} /> New test
      </button>
      {sim.project_title ? (
        <span className="chip outline truncate">
          <Icon name="film" size={13} strokeWidth={2} /> {sim.project_title}
        </span>
      ) : null}
    </div>
  );
  if (sim.status === 'failed') {
    return (
      <>
        {top}
        <ErrorNote error={new Error(sim.error || 'The simulation didn’t finish.')} />
      </>
    );
  }
  if (sim.status !== 'done' || !sim.result) {
    return (
      <>
        {top}
        <Watching text={progress} />
        <p className="small muted" style={{ margin: '12px 8px' }}>
          A thousand simulated viewers take a little while. You can leave this screen; the result waits for you.
        </p>
      </>
    );
  }
  if (rerun) return <SimStart parent={sim} />;

  const r = sim.result;
  const crowd = r.audience;
  const score = sim.engagement_score;
  const prev = crowd?.previous_engagement_score;
  return (
    <>
      {top}
      <section className={`score-hero blk-${scoreBlock(score === null || score === undefined ? null : score / 100)}`} aria-label="Engagement score">
        <div className="row between">
          <span className="eyebrow">Engagement score</span>
          {prev !== null && prev !== undefined && score !== null && score !== undefined ? (
            <span className="chip ink">
              {score >= prev ? '▲' : '▼'} {Math.abs(score - prev)} from your last take
            </span>
          ) : null}
        </div>
        <div className="score-big" role="img" aria-label={`Engagement score: ${score ?? 'unknown'}${score !== null && score !== undefined ? ' of 100' : ''}`}>
          {score ?? '—'}
          <small>/100</small>
        </div>
        <div className="score-track" aria-hidden="true">
          <i style={{ width: `${score ?? 0}%` }} />
          {prev !== null && prev !== undefined ? <b style={{ left: `${prev}%` }} title="Previous take" /> : null}
        </div>
        <p className="score-line">
          {score === null || score === undefined
            ? 'Needs at least 5 of your posted reels with public counts to compare with.'
            : `Beats ${score}% of your last ${crowd?.past_reels_scored ?? 0} reels on likes, comments and shares.`}
        </p>
      </section>
      <p className="label-sim" role="note">
        <Icon name="sparkle" size={12} /> {SIM_LABEL}
      </p>

      {crowd ? (
        <>
          <Predictions crowd={crowd} />
          <SkipCurve points={crowd.skip_curve} />
        </>
      ) : null}

      {r.best_time ? (
        <div className="best-time blk-lemon">
          <span className="circle ink" aria-hidden="true">
            <Icon name="clock" size={20} strokeWidth={2} />
          </span>
          <span className="pill-row-main">
            <small>Best time to post</small>
            <strong className="best-time-label">{r.best_time.label}</strong>
            <small className="wrap-text">{r.best_time.fact}</small>
          </span>
        </div>
      ) : null}

      {crowd ? <Explain ex={crowd.explain} /> : null}
      {(sim.edits ?? []).length ? <Edits sim={sim} /> : null}
      {crowd?.personas?.length ? <PersonaGroups crowd={crowd} simId={id} /> : null}

      {crowd?.comments.length ? (
        <section aria-label="Simulated comments">
          <SectionHead title="Simulated comments" hint="tap one to talk" />
          <div className="comments">
            {crowd.comments.slice(0, 12).map((c) => (
              <button key={c.agent_no} className="comment" onClick={() => setAgent(c.agent_no)} aria-label={`Talk to Agent ${c.agent_no}`}>
                <span className={`agent-dot blk-${PERSONA_BLOCK[c.color ?? ''] ?? 'paper'}`} aria-hidden="true">
                  {c.agent_no}
                </span>
                <span className="comment-body">
                  <small>
                    Agent {c.agent_no} · {c.segment}
                  </small>
                  <span className="comment-text">{c.text}</span>
                  {(c.replies ?? []).slice(0, 2).map((rp, i) => (
                    <span key={i} className="comment-reply">
                      <b>Agent {rp.agent_no}</b> {rp.text}
                    </span>
                  ))}
                </span>
                <span className="comment-likes">
                  <Icon name="likes" size={14} strokeWidth={2} />
                  {c.likes}
                </span>
              </button>
            ))}
          </div>
          <p className="label-sim">{SIM_LABEL}</p>
        </section>
      ) : null}

      {crowd?.segments.length ? (
        <section aria-label="Your AI audience">
          <SectionHead title="Your AI audience" hint={`${crowd.agents} agents`} />
          <div className="card paper">
            <div className="split-bar" aria-hidden="true">
              {crowd.segments.map((g, i) => (
                <i key={g.key} className={`blk-${segBlock(crowd, g.label, i)}`} style={{ flex: g.share }} />
              ))}
            </div>
            <div className="seg-legend">
              {crowd.segments.map((g, i) => (
                <div key={g.key} className="seg">
                  <i className={`blk-${segBlock(crowd, g.label, i)}`} aria-hidden="true" />
                  <span className="pill-row-main">
                    <strong>
                      {g.label} <span className="muted">{Math.round(g.share * 100)}%</span>
                    </strong>
                    {g.description ? <small>{g.description}</small> : null}
                  </span>
                </div>
              ))}
            </div>
            <p className="small muted" style={{ marginTop: 10 }}>
              Drawn from your {crowd.segments.length} follower personas, in proportion to each one’s share.
            </p>
          </div>
        </section>
      ) : null}

      <p className="small muted" style={{ margin: '18px 4px 12px' }}>
        {r.accuracy}
      </p>
      <button className="btn block ink big" onClick={() => setRerun(true)}>
        <Icon name="refresh" size={18} strokeWidth={2} /> Re-run with a new take
      </button>

      <AskThread messages={ask.messages} busy={ask.busy} />
      {agent !== null ? <AgentChat simId={id} agentNo={agent} onClose={() => setAgent(null)} /> : null}
    </>
  );
}

/** A segment's block: its persona's colour when the names match, else the rotation. */
function segBlock(crowd: S['SimAudienceResult'], label: string, i: number) {
  const p = (crowd.personas ?? []).find((x) => x.short_name === label || x.name === label);
  return p ? PERSONA_BLOCK[p.color] ?? blockAt(i) : blockAt(i);
}

/** While the audience watches: a field of 120 dots lighting up, and the current step. */
function Watching({ text }: { text: string }) {
  return (
    <section className="watching" role="status" aria-label={text}>
      <div className="dot-field" aria-hidden="true">
        {Array.from({ length: 120 }, (_, i) => (
          <i key={i} style={{ animationDelay: `${((i * 37) % 120) * 22}ms` }} />
        ))}
      </div>
      <span className="eyebrow" style={{ color: 'var(--lime)' }}>
        1,000 AI followers
      </span>
      <strong className="watching-text">{text}</strong>
    </section>
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

const METRIC = { views: 'Views', likes: 'Likes', comments: 'Comments', shares: 'Shares', saves: 'Saves' } as const;

const pct = (x: number | null | undefined) => (x === null || x === undefined ? '—' : `${(x * 100).toFixed(x < 0.1 ? 1 : 0)}%`);

/** v2.2: "How each follower group reacted" — one row per persona; tap for its own take. */
function PersonaGroups({ crowd, simId }: { crowd: S['SimAudienceResult']; simId: string }) {
  const [open, setOpen] = useState<string | null>(null);
  const g = (crowd.personas ?? []).find((x) => x.persona_id === open);
  return (
    <section aria-label="How each follower group reacted">
      <SectionHead title="How each group reacted" />
      <div className="stack" style={{ gap: 10 }}>
        {(crowd.personas ?? []).map((p) => {
          const kept = p.kept_watching ?? 0;
          return (
            <button key={p.persona_id} className={`group-card blk-${PERSONA_BLOCK[p.color] ?? 'paper'}`} onClick={() => setOpen(p.persona_id)} aria-label={`${p.name}: ${p.takeaway} Open their take`}>
              <div className="row" style={{ gap: 12 }}>
                <PersonaAvatar seed={p.avatar_seed} color={p.color as PersonaColor} mood={p.mood as Mood} size={48} name={p.name} share={p.share} decorative />
                <span className="pill-row-main">
                  <strong>{p.short_name}</strong>
                  <small>{p.agents} agents</small>
                </span>
                <span className="group-kept">
                  {pct(p.kept_watching)}
                  <small>kept watching</small>
                </span>
              </div>
              <div className="mini-bar on-block" aria-hidden="true">
                <i style={{ width: `${Math.round(kept * 100)}%` }} />
              </div>
              <div className="row wrap group-rates">
                <span>
                  <Icon name="likes" size={13} strokeWidth={2} /> {pct(p.rates.likes)}
                </span>
                <span>
                  <Icon name="comments" size={13} strokeWidth={2} /> {pct(p.rates.comments)}
                </span>
                <span>
                  <Icon name="shares" size={13} strokeWidth={2} /> {pct(p.rates.shares)}
                </span>
                <span>
                  <Icon name="bookmark" size={13} strokeWidth={2} /> {pct(p.rates.saves)}*
                </span>
                <span>{pct(p.watched_to_end)} to the end</span>
              </div>
              <p className="group-take">{p.takeaway}</p>
            </button>
          );
        })}
      </div>
      {(crowd.studio_compare ?? []).length ? (
        <div className="stack" style={{ gap: 4, marginTop: 10 }}>
          {(crowd.studio_compare ?? []).map((l) => (
            <p key={l} className="small light" style={{ margin: 0 }}>
              {l}
            </p>
          ))}
        </div>
      ) : null}
      <p className="small muted" style={{ margin: '10px 4px 0' }}>
        * Saves are simulated. {crowd.persona_label}
      </p>
      {g ? (
        <Overlay labelledBy="sim-persona" onClose={() => setOpen(null)}>
          <div className={`sheet-hero blk-${PERSONA_BLOCK[g.color] ?? 'paper'}`}>
            <div className="row between" style={{ alignItems: 'flex-start' }}>
              <PersonaAvatar seed={g.avatar_seed} color={g.color as PersonaColor} mood={g.mood as Mood} size={72} name={g.name} share={g.share} />
              <button className="circle white" onClick={() => setOpen(null)} aria-label="Close">
                <Icon name="close" size={18} />
              </button>
            </div>
            <h2 id="sim-persona" className="block-title">
              {g.name}
            </h2>
            <p style={{ margin: 0 }}>{g.takeaway}</p>
          </div>
          {g.opinion ? (
            <>
              <p className="pop-reaction" style={{ marginTop: 4 }}>
                {g.opinion.reaction_label}
              </p>
              <blockquote className="thought">“{g.opinion.opinion}”</blockquote>
              {g.opinion.win_them_over ? (
                <div className="note-card">
                  <span className="circle sm white" aria-hidden="true">
                    <Icon name="bolt" size={14} strokeWidth={2} />
                  </span>
                  <p>
                    <b>What would win them over:</b> {g.opinion.win_them_over}
                  </p>
                </div>
              ) : null}
            </>
          ) : null}
          <p className="label-sim" style={{ marginTop: 12 }}>
            {SIM_LABEL}
          </p>
          <PersonaChat personaId={g.persona_id} name={g.short_name} context="simulator" contextId={simId} />
          <PersonaLabel style={{ marginTop: 10 }} />
        </Overlay>
      ) : null}
    </section>
  );
}

const METRIC_ICON = { views: 'views', likes: 'likes', comments: 'comments', shares: 'shares', saves: 'bookmark' } as const;
const METRIC_BLOCK = { views: 'violet', likes: 'pink', comments: 'sky', shares: 'lime', saves: 'paper' } as const;

function Predictions({ crowd }: { crowd: S['SimAudienceResult'] }) {
  return (
    <section aria-label="Predicted ranges">
      <SectionHead title="First 7 days" hint="predicted range" />
      <div className="metric-grid">
        {crowd.predictions.map((p) => (
          <div key={p.metric} className={`metric blk-${METRIC_BLOCK[p.metric]}${p.metric === 'views' ? ' wide' : ''}`}>
            <div className="row between">
              <span className="metric-name">
                <Icon name={METRIC_ICON[p.metric]} size={15} strokeWidth={2} /> {METRIC[p.metric]}
              </span>
              {p.simulated ? <span className="chip white tiny">simulated</span> : null}
            </div>
            <b className="metric-range">{p.count === null || p.count === undefined ? 'unknown' : `${fmt(p.count_low)}–${fmt(p.count_high)}`}</b>
          </div>
        ))}
      </div>
      <p className="small muted" style={{ margin: '8px 4px 0' }}>
        From how the AI audience reacted, calibrated on your past reels. Saves have no public count, so they stay simulated.
      </p>
    </section>
  );
}

function SkipCurve({ points }: { points: S['SkipPoint'][] }) {
  if (points.length < 2) return null;
  const W = 320;
  const H = 120;
  const max = points[points.length - 1].t || 1;
  const d = points
    .map((p, i) => `${i ? 'L' : 'M'}${((p.t / max) * W).toFixed(1)},${(H - p.watching * H).toFixed(1)}`)
    .join(' ');
  const mid = points[Math.min(points.length - 1, 3)];
  const end = Math.round(points[points.length - 1].watching * 100);
  return (
    <section className="curve-card" aria-label="Skip curve">
      <div className="row between">
        <span className="eyebrow" style={{ color: 'var(--lime)' }}>
          Who keeps watching
        </span>
        <span className="chip clear">{end}% to the end</span>
      </div>
      <div className="curve-big">
        {Math.round(mid.watching * 100)}%<small> still watching at {mmss(mid.t)}</small>
      </div>
      <svg viewBox={`0 -6 ${W} ${H + 24}`} width="100%" role="img" aria-label={`Share of agents still watching each second; ${end}% reach the end.`}>
        <line x1={0} y1={H} x2={W} y2={H} stroke="rgba(255,255,255,.2)" />
        <line x1={0} y1={H / 2} x2={W} y2={H / 2} stroke="rgba(255,255,255,.12)" strokeDasharray="4 4" />
        <path d={`${d} L${W},${H} L0,${H} Z`} fill="var(--lime)" opacity={0.18} />
        <path d={d} fill="none" stroke="var(--lime)" strokeWidth={3} strokeLinejoin="round" strokeLinecap="round" />
        <text x={0} y={H + 16} fontSize={11} fill="rgba(255,255,255,.6)">
          0:00
        </text>
        <text x={W} y={H + 16} fontSize={11} fill="rgba(255,255,255,.6)" textAnchor="end">
          {mmss(max)}
        </text>
      </svg>
    </section>
  );
}

function Explain({ ex }: { ex: S['AudienceExplain'] }) {
  const block = (title: string, items: S['TimedText'][], tone: string, icon: IconName) =>
    items.length ? (
      <section className={`panel-block ${tone}`} aria-label={title}>
        <h3 className="panel-title">
          <span className="circle sm white" aria-hidden="true">
            <Icon name={icon} size={15} strokeWidth={2.2} />
          </span>
          {title}
        </h3>
        {items.map((it, i) => (
          <div key={i} className="pill-row static">
            {it.at_s !== null && it.at_s !== undefined ? <span className="time-chip">{mmss(it.at_s)}</span> : null}
            <span className="pill-row-main">
              <strong className="wrap-text">{it.text}</strong>
            </span>
          </div>
        ))}
      </section>
    ) : null;
  return (
    <>
      {block('What’s working', ex.working ?? [], 'lime', 'check')}
      {block('What’s holding it back', ex.holding ?? [], 'coral', 'close')}
      {block('What to change', ex.edits ?? [], 'sky', 'bolt')}
    </>
  );
}

const EFFORT = { edit_only: 'Edit only', reshoot: 'Reshoot', caption: 'Caption only' } as Record<string, string>;

function Edits({ sim }: { sim: S['Simulation'] }) {
  const s = useApp();
  const qc = useQueryClient();
  const apply = useMutation({
    mutationFn: (editId: string) => api<S['EditApplied']>(`/simulations/${sim.id}/edits/${editId}/apply`, { body: {} }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['sim', sim.id] });
      s.showToast(r.job_id ? 'Sent to your Studio draft.' : 'Marked. Make the change when you record again.');
    },
  });
  return (
    <section aria-label="Edits Curo can make for you">
      <SectionHead title="Edits Curo can make" />
      <div className="stack" style={{ gap: 10 }}>
        {(sim.edits ?? []).slice(0, 3).map((e) => {
          return (
            <div key={e.id} className="edit-card">
              <div className="row between">
                <span className="chip outline">{EFFORT[e.effort] ?? e.effort}</span>
              </div>
              <h3 className="edit-title">{e.title}</h3>
              <p className="small light" style={{ margin: 0 }}>
                {e.description}
              </p>
              {e.frame_label ? (
                <p className="small muted" style={{ margin: '6px 0 0' }}>
                  <Icon name="grid" size={12} strokeWidth={2} /> {e.frame_label}
                </p>
              ) : null}
              <button className={`btn small ${e.applied ? 'ghost' : 'ink'}`} style={{ marginTop: 12 }} disabled={e.applied || apply.isPending} onClick={() => apply.mutate(e.id)}>
                {e.applied ? (
                  <>
                    <Icon name="check" size={14} strokeWidth={3} /> Applied
                  </>
                ) : sim.project_id ? (
                  'Apply to my draft'
                ) : (
                  'Mark as done'
                )}
              </button>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function AgentChat({ simId, agentNo, onClose }: { simId: string; agentNo: number; onClose: () => void }) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ['agent', simId, agentNo],
    queryFn: () => api<S['AgentOut']>(`/simulations/${simId}/agents/${agentNo}`),
  });
  const [text, setText] = useState('');
  const send = useMutation({
    mutationFn: (message: string) => api<S['AgentChatOut']>(`/simulations/${simId}/agents/${agentNo}/chat`, { body: { message } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agent', simId, agentNo] }),
  });
  const a = q.data;
  const left = a?.messages_left ?? 0;
  const pending = send.isPending ? send.variables : null;
  return (
    <Overlay labelledBy="agent-title" onClose={onClose}>
        <div className="row between">
          <h2 id="agent-title" style={{ margin: 0, fontSize: 20 }}>
            Agent {agentNo}
            {a ? ` · ${a.segment_label}` : ''}
          </h2>
          <button className="circle sm" onClick={onClose} aria-label="Close">
            <Icon name="close" size={18} />
          </button>
        </div>
        <p className="label-sim" style={{ marginTop: 12 }}>
          A simulated viewer from CURO’s AI audience. Not a real person.
        </p>
        {q.isLoading ? <Loading /> : null}
        {a ? (
          <>
            <p className="small light">{a.persona_text}</p>
            <p className="small" style={{ marginTop: 6 }}>
              {String((a.reaction as { reason?: string }).reason ?? '')}
            </p>
            <div className="stack" style={{ margin: '14px 0', gap: 8 }} aria-live="polite">
              {(a.chat ?? []).map((m, i) => (
                <div key={i} className={`bubble ${m.role === 'user' ? 'me' : 'them'}`}>
                  {m.content}
                </div>
              ))}
              {pending ? (
                <>
                  <div className="bubble me">{pending}</div>
                  <div className="bubble them">…</div>
                </>
              ) : null}
            </div>
            <form
              className="row"
              onSubmit={(e) => {
                e.preventDefault();
                const t = text.trim();
                if (!t || left <= 0) return;
                send.mutate(t);
                setText('');
              }}
            >
              <input
                className="field"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={left > 0 ? 'Ask why they stopped, what would make them share…' : 'No messages left for this simulation'}
                aria-label="Message to the agent"
                disabled={left <= 0}
                maxLength={500}
              />
              <button className="circle violet" type="submit" aria-label="Send" disabled={left <= 0 || send.isPending}>
                <Icon name="send" size={20} />
              </button>
            </form>
            <p className="small muted" style={{ marginTop: 8 }}>
              {left} of 10 agent messages left for this simulation.
            </p>
          </>
        ) : null}
    </Overlay>
  );
}

function fmt(n: number | null | undefined) {
  if (n === null || n === undefined) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 10_000) return `${Math.round(n / 1000)}K`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

function mmss(s: number) {
  const t = Math.max(0, Math.round(s));
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`;
}
