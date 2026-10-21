'use client';
/** One opportunity area: the score and its parts, the evidence, what's trending, and Start. */
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { ErrorNote, Loading } from '@/components/Chrome';
import { Icon } from '@/components/Icon';
import { ScoreRing } from '@/components/ScoreRing';
import { api, type S } from '@/lib/api';
import { useOpportunity } from '@/lib/hooks';
import { useApp } from '@/state/app';

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
  return (
    <>
      <div className="row" style={{ gap: 16, marginBottom: 16 }}>
        <ScoreRing value={o.score_shown} max={10} size={104} label="Opportunity score" sub="of 10" />
        <div>
          <span className="pill lav">{o.tag}</span>
          <h2 style={{ margin: '8px 0 0', fontSize: 24, letterSpacing: '-0.01em' }}>{o.name}</h2>
          {o.window_ends_on ? (
            <p className="small muted" style={{ margin: '4px 0 0' }}>
              Window until {new Date(o.window_ends_on).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
            </p>
          ) : null}
        </div>
      </div>
      <p className="light" style={{ fontSize: 16, lineHeight: 1.5, margin: '0 4px 18px' }}>
        {o.description}
      </p>

      <button className="btn block" onClick={() => start.mutate()} disabled={start.isPending}>
        <Icon name="sparkle" size={18} /> {start.isPending ? 'Starting…' : 'Start in Studio'}
      </button>

      <h3 className="section-title" style={{ fontSize: 18, marginTop: 24 }}>
        Why it scores {o.score_shown}
      </h3>
      <div className="card">
        {o.parts.map((p) => (
          <div key={p.key} style={{ marginBottom: 14 }}>
            <div className="row between small">
              <span style={{ fontWeight: 600 }}>{p.name}</span>
              <span className="muted">{Math.round(p.share * 100)}% of the score</span>
            </div>
            <div className="bar" style={{ margin: '6px 0' }}>
              <span style={{ width: `${Math.round(p.value * 100)}%` }} />
            </div>
            {p.facts.slice(0, 2).map((f) => (
              <p key={f} className="small light">
                {f}
              </p>
            ))}
          </div>
        ))}
      </div>

      {o.fit.length ? (
        <div className="card gray">
          <h3 style={{ fontSize: 16 }}>How it fits you</h3>
          {(o.fit as { k: string; t: string }[]).map((f) => (
            <p key={f.k} style={{ marginTop: 6 }}>
              <strong>{f.k}:</strong> <span className="light">{f.t}</span>
            </p>
          ))}
        </div>
      ) : null}

      {(o.trending ?? []).length ? (
        <>
          <h3 className="section-title" style={{ fontSize: 18, marginTop: 20 }}>
            What’s trending in your niche
          </h3>
          {(o.trending ?? []).map((t) => (
            <div key={t.name} className="card">
              <div className="row between">
                <h3 style={{ fontSize: 16, margin: 0 }}>{t.name}</h3>
                <span className="pill pink">{t.saturation === 'unknown' ? 'new' : t.saturation}</span>
              </div>
              <p className="light small" style={{ marginTop: 6 }}>
                {t.why_rising}
              </p>
            </div>
          ))}
        </>
      ) : null}

      <button className="btn block ghost" style={{ marginTop: 12 }} onClick={() => dismiss.mutate()} disabled={dismiss.isPending}>
        Not for me
      </button>
    </>
  );
}
