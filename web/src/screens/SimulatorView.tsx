'use client';
/**
 * The Simulator (v2): upload the recorded video; CURO's AI audience — personas built from the
 * creator's own comments — watches it, reacts, comments and replies. The result leads with the
 * engagement score, then predicted ranges, the skip curve, the best time to post, what's
 * working / holding it back / to edit (with timestamps), and the simulated comments, each
 * agent one tap away. Everything the agents say is labelled simulated.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';

import { AskThread, useAskCuro } from '@/components/AskCuro';
import { ErrorNote, Loading } from '@/components/Chrome';
import { Overlay } from '@/components/Overlay';
import { Icon } from '@/components/Icon';
import { ScoreRing } from '@/components/ScoreRing';
import { api, uploadVideo, waitForJob, type S } from '@/lib/api';
import { useProject, useSimulation } from '@/lib/hooks';
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

  return (
    <>
      <h2 className="section-title">{parent ? 'Re-run with a new take' : 'Simulator'}</h2>
      <p className="section-sub">
        Test a recorded reel on an AI audience built from your own comments, before you post.
      </p>
      {busy ? <Loading text={busy} /> : null}

      {project.data && !parent ? (
        <label className="card gray row between" style={{ cursor: 'pointer' }}>
          <span>
            <strong>Link to your draft</strong>
            <br />
            <span className="small muted">{project.data.title || project.data.opportunity?.name}</span>
          </span>
          <input type="checkbox" checked={link} onChange={(e) => setLink(e.target.checked)} style={{ width: 22, height: 22 }} />
        </label>
      ) : null}

      <label htmlFor="caption" className="small" style={{ fontWeight: 600, margin: '8px 4px', display: 'block' }}>
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

      <input
        ref={file}
        type="file"
        accept="video/mp4,video/quicktime,.mp4,.mov"
        hidden
        onChange={(e) => onFile(e.target.files?.[0])}
      />
      <button className="btn block" style={{ marginTop: 14 }} disabled={!!busy} onClick={() => file.current?.click()}>
        <Icon name="upload" size={18} /> Upload your video (MP4 or MOV, up to 90 seconds)
      </button>

      {samples.data?.length ? (
        <>
          <h3 className="section-title" style={{ fontSize: 17, marginTop: 22 }}>
            Or try a sample
          </h3>
          {samples.data.map((v) => (
            <button key={v.name} className="card tap" disabled={!!busy} onClick={() => pickSample(v.name)}>
              <div className="row between">
                <h3 style={{ margin: 0, fontSize: 16 }}>{v.title}</h3>
                <span className="small muted">{Math.round(v.duration_s)}s</span>
              </div>
              <p className="small light" style={{ marginTop: 6 }}>
                {v.description}
              </p>
            </button>
          ))}
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
      placeholder: 'Ask about this result',
      hint: 'For example: why do people stop at the start?',
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
    <div className="row between" style={{ marginBottom: 12 }}>
      <button className="pill" onClick={() => s.openSim(null)}>
        <Icon name="back" size={16} /> New simulation
      </button>
      {sim.project_title ? <span className="small muted">{sim.project_title}</span> : null}
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
        <Loading text={progress} />
        <p className="small muted" style={{ margin: '0 8px' }}>
          A thousand simulated viewers take a little while. You can leave this screen; the result waits for you.
        </p>
      </>
    );
  }
  if (rerun) return <SimStart parent={sim} />;

  const r = sim.result;
  const crowd = r.audience;
  return (
    <>
      {top}
      <p className="label-sim" role="note">
        {SIM_LABEL}
      </p>

      <section className="card lav" aria-label="Engagement score">
        <div className="row" style={{ gap: 16 }}>
          <ScoreRing value={sim.engagement_score} size={116} label="Engagement score" sub="of 100" />
          <div>
            <h3 style={{ margin: 0 }}>Engagement score</h3>
            <p className="light small" style={{ marginTop: 4 }}>
              {sim.engagement_score === null || sim.engagement_score === undefined
                ? 'Needs at least 5 of your posted reels with public counts to compare with.'
                : `Beats ${sim.engagement_score}% of your last ${crowd?.past_reels_scored ?? 0} reels on likes, comments and shares.`}
            </p>
            {crowd?.previous_engagement_score !== null && crowd?.previous_engagement_score !== undefined ? (
              <p className="small" style={{ marginTop: 6, fontWeight: 600 }}>
                Previous take: {crowd.previous_engagement_score} → now {sim.engagement_score ?? '—'}
              </p>
            ) : null}
          </div>
        </div>
      </section>

      {crowd ? (
        <>
          <Predictions crowd={crowd} />
          <SkipCurve points={crowd.skip_curve} />
        </>
      ) : null}

      {r.best_time ? (
        <div className="card gray">
          <div className="row">
            <Icon name="clock" />
            <h3 style={{ margin: 0, fontSize: 16 }}>Best time to post: {r.best_time.label}</h3>
          </div>
          <p className="small light" style={{ marginTop: 6 }}>
            {r.best_time.fact}
          </p>
        </div>
      ) : null}

      {crowd ? <Explain ex={crowd.explain} /> : null}

      {crowd?.comments.length ? (
        <>
          <h3 className="section-title" style={{ fontSize: 18, marginTop: 20 }}>
            Simulated comments
          </h3>
          <p className="label-sim">{SIM_LABEL}</p>
          {crowd.comments.slice(0, 12).map((c) => (
            <button key={c.agent_no} className="card tap" onClick={() => setAgent(c.agent_no)} aria-label={`Talk to Agent ${c.agent_no}`}>
              <p className="small muted" style={{ fontWeight: 600 }}>
                Agent {c.agent_no} · {c.segment}
              </p>
              <p style={{ marginTop: 4 }}>{c.text}</p>
              <div className="row small muted" style={{ marginTop: 6, gap: 12 }}>
                <span className="row" style={{ gap: 4 }}>
                  <Icon name="likes" size={14} /> {c.likes}
                </span>
                {(c.replies ?? []).length ? <span>{(c.replies ?? []).length} replies</span> : null}
                <span style={{ marginLeft: 'auto' }}>Tap to talk</span>
              </div>
              {(c.replies ?? []).slice(0, 2).map((rp, i) => (
                <p key={i} className="small light" style={{ marginTop: 6, paddingLeft: 12, borderLeft: '2px solid var(--gray)' }}>
                  Agent {rp.agent_no} · {rp.segment}: {rp.text}
                </p>
              ))}
            </button>
          ))}
        </>
      ) : null}

      {crowd?.segments.length ? (
        <div className="card">
          <h3 style={{ fontSize: 16 }}>Your AI audience</h3>
          <p className="small muted">
            {crowd.agents} agents in {crowd.segments.length} groups, built from your comments.
          </p>
          {crowd.segments.map((g) => (
            <div key={g.key} style={{ marginTop: 10 }}>
              <div className="row between small">
                <strong>{g.label}</strong>
                <span className="muted">{Math.round(g.share * 100)}%</span>
              </div>
              <div className="bar" style={{ marginTop: 4 }}>
                <span style={{ width: `${Math.round(g.share * 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {(sim.edits ?? []).length ? <Edits sim={sim} /> : null}

      <p className="small muted" style={{ margin: '8px 4px 16px' }}>
        {r.accuracy}
      </p>
      <button className="btn block lav" onClick={() => setRerun(true)}>
        <Icon name="refresh" size={18} /> Re-run with a new take
      </button>

      <AskThread messages={ask.messages} busy={ask.busy} />
      {agent !== null ? <AgentChat simId={id} agentNo={agent} onClose={() => setAgent(null)} /> : null}
    </>
  );
}

const METRIC = { views: 'Views', likes: 'Likes', comments: 'Comments', shares: 'Shares', saves: 'Saves' } as const;

function Predictions({ crowd }: { crowd: S['SimAudienceResult'] }) {
  return (
    <section className="card" aria-label="Predicted ranges">
      <h3 style={{ fontSize: 16 }}>Predicted in the first 7 days</h3>
      {crowd.predictions.map((p) => (
        <div key={p.metric} className="row between" style={{ padding: '8px 0', borderBottom: '1px solid var(--gray)' }}>
          <span>
            {METRIC[p.metric]}
            {p.simulated ? <span className="pill pink" style={{ height: 22, marginLeft: 8, fontSize: 11 }}>simulated</span> : null}
          </span>
          <span style={{ fontWeight: 600 }}>
            {p.count === null || p.count === undefined ? (
              <span className="muted" style={{ fontWeight: 400 }}>
                unknown
              </span>
            ) : (
              `${fmt(p.count_low)}–${fmt(p.count_high)}`
            )}
          </span>
        </div>
      ))}
      <p className="small muted" style={{ marginTop: 8 }}>
        Ranges come from how the AI audience reacted, calibrated on your past reels. Saves have no public count to check
        against, so they stay simulated.
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
  return (
    <section className="card" aria-label="Skip curve">
      <h3 style={{ fontSize: 16 }}>Who keeps watching</h3>
      <svg viewBox={`0 -6 ${W} ${H + 24}`} width="100%" role="img" aria-label={`Share of agents still watching each second; ${Math.round(points[points.length - 1].watching * 100)}% reach the end.`}>
        <line x1={0} y1={H} x2={W} y2={H} stroke="var(--gray)" />
        <line x1={0} y1={0} x2={W} y2={0} stroke="var(--gray)" strokeDasharray="4 4" />
        <path d={`${d} L${W},${H} L0,${H} Z`} fill="var(--lavender)" opacity={0.6} />
        <path d={d} fill="none" stroke="var(--blue)" strokeWidth={2.5} strokeLinejoin="round" />
        <text x={0} y={H + 16} fontSize={11} fill="var(--ink)">0:00</text>
        <text x={W} y={H + 16} fontSize={11} fill="var(--ink)" textAnchor="end">{mmss(max)}</text>
      </svg>
      <p className="small light">
        {Math.round(mid.watching * 100)}% still watching at {mmss(mid.t)}; {Math.round(points[points.length - 1].watching * 100)}% to the end.
      </p>
    </section>
  );
}

function Explain({ ex }: { ex: S['AudienceExplain'] }) {
  const block = (title: string, items: S['TimedText'][], tone: string) =>
    items.length ? (
      <div className={`card ${tone}`}>
        <h3 style={{ fontSize: 16 }}>{title}</h3>
        {items.map((it, i) => (
          <p key={i} style={{ marginTop: 8 }}>
            {it.at_s !== null && it.at_s !== undefined ? <span className="pill white" style={{ height: 24, marginRight: 8 }}>{mmss(it.at_s)}</span> : null}
            {it.text}
          </p>
        ))}
      </div>
    ) : null;
  return (
    <>
      {block('What’s working', ex.working ?? [], '')}
      {block('What’s holding it back', ex.holding ?? [], 'pink')}
      {block('What to change', ex.edits ?? [], 'gray')}
    </>
  );
}

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
    <section className="card">
      <h3 style={{ fontSize: 16 }}>Edits Curo can make for you</h3>
      {(sim.edits ?? []).slice(0, 3).map((e) => (
        <div key={e.id} style={{ marginTop: 12 }}>
          <p style={{ fontWeight: 600 }}>{e.title}</p>
          <p className="small light">{e.description}</p>
          <button className="btn small ghost" style={{ marginTop: 8 }} disabled={e.applied || apply.isPending} onClick={() => apply.mutate(e.id)}>
            {e.applied ? 'Applied' : sim.project_id ? 'Apply to my draft' : 'Mark as done'}
          </button>
        </div>
      ))}
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
              <button className="circle blue" type="submit" aria-label="Send" disabled={left <= 0 || send.isPending}>
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
