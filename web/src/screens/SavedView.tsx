'use client';
/** Saved: the opportunity areas and Studio drafts the creator kept. */
import { ErrorNote, Loading } from '@/components/Chrome';
import { Icon } from '@/components/Icon';
import { useSaved } from '@/lib/hooks';
import { useApp } from '@/state/app';

const STEP = { ideas: 'Ideas', idea: 'Idea', script: 'Script', storyboard: 'Storyboard', caption: 'Caption', final: 'Ready' };

export function SavedView() {
  const q = useSaved();
  const s = useApp();
  if (q.isLoading) return <Loading />;
  if (q.error || !q.data) return <ErrorNote error={q.error} onRetry={() => q.refetch()} />;
  const opportunities = q.data.opportunities ?? [];
  const drafts = q.data.drafts ?? [];
  return (
    <>
      <h2 className="section-title">Drafts</h2>
      {drafts.length === 0 ? <p className="section-sub">Drafts you save in Studio show up here.</p> : null}
      {drafts.map((d) => (
        <button key={d.id} className="card tap" onClick={() => s.openProject(d.id)}>
          <div className="row between">
            <h3 style={{ margin: 0 }}>{d.title}</h3>
            <Icon name="chevronRight" />
          </div>
          <p className="small muted" style={{ marginTop: 6 }}>
            {STEP[d.step]}
            {d.opportunity ? ` · ${d.opportunity}` : ''}
          </p>
        </button>
      ))}
      <h2 className="section-title" style={{ marginTop: 24 }}>
        Opportunity areas
      </h2>
      {opportunities.length === 0 ? (
        <p className="section-sub">Tap the bookmark on an opportunity area to keep it.</p>
      ) : null}
      {opportunities.map((o) => (
        <button
          key={o.id}
          className="card tap"
          onClick={() => {
            s.setSaved(false);
            s.nav('home');
            s.openOpp(o.id);
          }}
        >
          <div className="row between">
            <span className="pill lav">{o.tag}</span>
            <span className="small muted">
              {o.window_passed ? 'Window passed' : `${Math.round(o.score_today)}/10 today`}
              {o.score_when_saved !== null && o.score_when_saved !== undefined
                ? ` · ${Math.round(o.score_when_saved)} when saved`
                : ''}
            </span>
          </div>
          <h3 style={{ marginTop: 10 }}>{o.name}</h3>
        </button>
      ))}
    </>
  );
}
