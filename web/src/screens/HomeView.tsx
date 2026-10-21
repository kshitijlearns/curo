'use client';
/** Home (v2): Opportunity areas, then Trending for you. No carousel, no Insights page. */
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { ErrorNote, Loading } from '@/components/Chrome';
import { Icon } from '@/components/Icon';
import { api, type S } from '@/lib/api';
import { useMe, useOpportunities, useTrends } from '@/lib/hooks';
import { useApp } from '@/state/app';

export function HomeView() {
  const me = useMe();
  const opps = useOpportunities();
  const trends = useTrends();
  const s = useApp();
  const qc = useQueryClient();
  const refresh = useMutation({
    mutationFn: () => api<S['RefreshOut']>('/reels/refresh', { body: {} }),
    onSuccess: (r) => {
      s.showToast(r.status === 'queued' ? 'Fetching your latest numbers…' : 'Your data is up to date.');
      qc.invalidateQueries();
    },
  });

  const name = me.data?.account?.username;
  return (
    <>
      <div className="row between" style={{ margin: '0 4px 4px' }}>
        <p className="light" style={{ margin: 0, fontSize: 16 }}>
          {name ? `Hi @${name}` : 'Hi'}
        </p>
        <button className="pill" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
          <Icon name="refresh" size={16} /> Refresh
        </button>
      </div>

      <h2 className="section-title">Opportunity areas</h2>
      <p className="section-sub">What to make next, from your reels, your audience and what’s rising.</p>
      {opps.isLoading ? <Loading text="Finding your opportunities…" /> : null}
      {opps.error ? <ErrorNote error={opps.error} onRetry={() => opps.refetch()} /> : null}
      {opps.data && opps.data.length === 0 ? (
        <div className="card gray">
          <p className="light">
            Curo is still reading your reels. Opportunity areas appear after the first nightly run.
          </p>
        </div>
      ) : null}
      {opps.data?.map((o, i) => (
        <button
          key={o.id}
          className={`card tap ${i === 0 ? 'lav' : ''}`}
          style={{ animationDelay: `${i * 60}ms` }}
          onClick={() => s.openOpp(o.id)}
        >
          <div className="row between" style={{ marginBottom: 10 }}>
            <span className={`pill ${i === 0 ? 'white' : 'lav'}`}>{o.tag}</span>
            <span className="row" style={{ gap: 4 }}>
              <span className="score" style={{ fontSize: 28 }}>
                {o.score_shown}
              </span>
              <span className="muted small">/10</span>
            </span>
          </div>
          <h3>{o.name}</h3>
          <p className="light">{o.card}</p>
          {o.saved ? (
            <p className="small" style={{ marginTop: 8, fontWeight: 600 }}>
              Saved
            </p>
          ) : null}
        </button>
      ))}

      <h2 className="section-title" style={{ marginTop: 28 }}>
        Trending for you
      </h2>
      <p className="section-sub">Picking up in your niche this week, ranked for your reels.</p>
      {trends.isLoading ? <Loading text="Reading the trend feed…" /> : null}
      {trends.data && trends.data.length === 0 ? (
        <div className="card gray">
          <p className="light">Nothing new is picking up in your niche today. Check back tomorrow.</p>
        </div>
      ) : null}
      {trends.data?.map((t, i) => (
        <TrendCard key={t.id} t={t} delay={i * 60} />
      ))}
    </>
  );
}

function TrendCard({ t, delay }: { t: S['TrendCard']; delay: number }) {
  const s = useApp();
  const qc = useQueryClient();
  const start = useMutation({
    mutationFn: (angle: string) => api<S['ProjectStarted']>('/projects', { body: { idea_text: angle } }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['me'] });
      s.openProject(r.project_id);
    },
  });
  return (
    <article className="card" style={{ animationDelay: `${delay}ms` }}>
      <div className="row between" style={{ marginBottom: 8 }}>
        <span className="pill pink">{t.saturation === 'unknown' ? 'New' : `${cap(t.saturation)} competition`}</span>
        {t.window_end ? <span className="small muted">until {fmtDate(t.window_end)}</span> : null}
      </div>
      <h3>{t.name}</h3>
      <p className="light">{t.summary}</p>
      <p style={{ marginTop: 8, fontSize: 14 }}>{t.why_rising}</p>
      <p className="small muted" style={{ marginTop: 6 }}>
        {t.why_it_fits}
      </p>
      {t.example_angles.length ? (
        <div className="stack" style={{ marginTop: 12, gap: 8 }}>
          {t.example_angles.map((a) => (
            <button
              key={a}
              className="pill white"
              style={{ border: '1px solid var(--gray)', height: 'auto', minHeight: 34, padding: '6px 12px', whiteSpace: 'normal', textAlign: 'left', justifyContent: 'space-between' }}
              onClick={() => start.mutate(a)}
              disabled={start.isPending}
              aria-label={`Start a project: ${a}`}
            >
              <span style={{ fontWeight: 400 }}>{a}</span>
              <Icon name="arrowRight" size={16} />
            </button>
          ))}
        </div>
      ) : null}
      {(t.hashtags ?? []).length ? (
        <p className="small muted" style={{ marginTop: 10 }}>
          {(t.hashtags ?? []).slice(0, 5).map((h) => `#${h}`).join(' ')}
        </p>
      ) : null}
    </article>
  );
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}
