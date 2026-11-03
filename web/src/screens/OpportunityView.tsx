'use client';
/** One opportunity area (v3): a big score on a colour block, what the score is made of as one
 *  stacked bar and four tiles, how it fits you, what's trending, and Start. */
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { Chip, ErrorNote, Loading } from '@/components/Chrome';
import { Icon, type IconName } from '@/components/Icon';
import { api, type S } from '@/lib/api';
import { useOpportunity } from '@/lib/hooks';
import { useApp } from '@/state/app';

const PART_BLOCK: Record<string, string> = { F: 'lemon', D: 'pink', T: 'lime', O: 'sky' };
const FIT_ICON: Record<string, IconName> = { 'Your content': 'film', Timing: 'clock', Audience: 'users', 'Room left': 'trend' };

export function OpportunityView({ id }: { id: string }) {
  const q = useOpportunity(id);
  const s = useApp();
  const qc = useQueryClient();
  const start = useMutation({
    mutationFn: () => api<S['ProjectStarted']>('/projects', { body: { opportunity_id: id } }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['me'] });
      s.openProject(r.project_id);
    },
  });
  const dismiss = useMutation({
    mutationFn: () => api<void>(`/opportunities/${id}/dismiss`, { body: {} }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['opps'] });
      s.showToast('Dismissed. Curo won’t show it again.');
      s.openOpp(null);
    },
  });

  if (q.isLoading) return <Loading />;
  if (q.error || !q.data) return <ErrorNote error={q.error} onRetry={() => q.refetch()} />;
  const o = q.data;
  const total = o.parts.reduce((a, p) => a + p.share, 0) || 1;
  return (
    <>
      <section className="opp-hero blk-violet">
        <div className="row between">
          <Chip>{o.tag}</Chip>
          {o.window_ends_on ? (
            <Chip>
              <Icon name="clock" size={14} strokeWidth={2} /> until {new Date(o.window_ends_on).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
            </Chip>
          ) : null}
        </div>
        <div className="opp-score" role="img" aria-label={`Opportunity score: ${o.score_shown} of 10`}>
          {o.score_shown}
          <small>/10</small>
        </div>
        <h1 className="block-title" style={{ fontSize: 32 }}>
          {o.name}
        </h1>
        <p className="opp-desc">{o.description}</p>
      </section>

      <button className="btn block ink big" onClick={() => start.mutate()} disabled={start.isPending}>
        <Icon name="sparkle" size={18} /> {start.isPending ? 'Starting…' : 'Start in Studio'}
      </button>

      <h2 className="section-label">Why it scores {o.score_shown}</h2>
      <div className="split-bar" aria-hidden="true">
        {o.parts.map((p) => (
          <i key={p.key} className={`blk-${PART_BLOCK[p.key] ?? 'paper'}`} style={{ flex: p.share / total }} />
        ))}
      </div>
      <div className="part-grid">
        {o.parts.map((p) => (
          <div key={p.key} className={`part-tile blk-${PART_BLOCK[p.key] ?? 'paper'}`}>
            <div className="row between">
              <span className="part-name">{p.name}</span>
              <span className="part-share">{Math.round(p.share * 100)}%</span>
            </div>
            <div className="mini-bar" role="meter" aria-label={`${p.name}: ${Math.round(p.value * 100)} of 100`} aria-valuenow={Math.round(p.value * 100)} aria-valuemin={0} aria-valuemax={100}>
              <i style={{ width: `${Math.round(p.value * 100)}%` }} />
            </div>
            {p.facts[0] ? <p className="part-fact">{p.facts[0]}</p> : null}
          </div>
        ))}
      </div>

      {o.fit.length ? (
        <>
          <h2 className="section-label">How it fits you</h2>
          <div className="panel-block paper">
            {(o.fit as { k: string; t: string }[]).map((f) => (
              <div key={f.k} className="pill-row static">
                <span className="circle sm white" aria-hidden="true">
                  <Icon name={FIT_ICON[f.k] ?? 'check'} size={16} strokeWidth={2} />
                </span>
                <span className="pill-row-main">
                  <small>{f.k}</small>
                  <strong className="wrap-text">{f.t}</strong>
                </span>
              </div>
            ))}
          </div>
        </>
      ) : null}

      {(o.trending ?? []).length ? (
        <>
          <h2 className="section-label">Trending in your niche</h2>
          <div className="stack" style={{ gap: 8 }}>
            {(o.trending ?? []).map((t) => (
              <div key={t.name} className="trend-row">
                <span className={`heat heat-${t.saturation}`} aria-hidden="true">
                  <Icon name="trend" size={16} strokeWidth={2.2} />
                </span>
                <span className="pill-row-main">
                  <strong>{t.name}</strong>
                  <small>{t.why_rising}</small>
                </span>
                <span className="chip outline">{t.saturation === 'unknown' ? 'new' : t.saturation}</span>
              </div>
            ))}
          </div>
        </>
      ) : null}

      <button className="btn block ghost" style={{ marginTop: 20 }} onClick={() => dismiss.mutate()} disabled={dismiss.isPending}>
        Not for me
      </button>
    </>
  );
}
