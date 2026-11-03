'use client';
/** Saved (v3, inside Account): the Studio drafts and opportunity areas the creator kept, behind a
 *  two-way switch, as white rows on a coloured panel. */
import { useState } from 'react';

import { ErrorNote, Loading } from '@/components/Chrome';
import { Icon } from '@/components/Icon';
import { useSaved } from '@/lib/hooks';
import { useApp } from '@/state/app';

const STEP = { ideas: 'Ideas', idea: 'Idea', script: 'Script', storyboard: 'Storyboard', caption: 'Caption', final: 'Ready' };
const STEP_N = { ideas: 1, idea: 1, script: 2, storyboard: 3, caption: 4, final: 4 };

export function SavedView() {
  const q = useSaved();
  const s = useApp();
  const [which, setWhich] = useState<'drafts' | 'opps'>('drafts');
  if (q.isLoading) return <Loading />;
  if (q.error || !q.data) return <ErrorNote error={q.error} onRetry={() => q.refetch()} />;
  const opportunities = q.data.opportunities ?? [];
  const drafts = q.data.drafts ?? [];
  return (
    <section aria-label="Saved">
      <div className="switch" role="tablist" aria-label="Saved">
        <button role="tab" aria-selected={which === 'drafts'} onClick={() => setWhich('drafts')}>
          <Icon name="film" size={18} strokeWidth={2} /> Drafts <b>{drafts.length}</b>
        </button>
        <button role="tab" aria-selected={which === 'opps'} onClick={() => setWhich('opps')}>
          <Icon name="bookmark" size={18} strokeWidth={2} /> Opportunities <b>{opportunities.length}</b>
        </button>
      </div>
      <div className={`panel-block ${which === 'drafts' ? 'sky' : 'lime'}`}>
        {which === 'drafts' ? (
          drafts.length === 0 ? (
            <Empty icon="film" text="Drafts you save in Studio land here." />
          ) : (
            drafts.map((d) => (
              <button key={d.id} className="pill-row" onClick={() => s.openProject(d.id)}>
                <span className="step-dot" aria-hidden="true">
                  {STEP_N[d.step]}/4
                </span>
                <span className="pill-row-main">
                  <strong>{d.title}</strong>
                  <small>
                    {STEP[d.step]}
                    {d.opportunity ? ` · ${d.opportunity}` : ''}
                  </small>
                </span>
                <Icon name="chevronRight" size={18} strokeWidth={2} />
              </button>
            ))
          )
        ) : opportunities.length === 0 ? (
          <Empty icon="bookmark" text="Tap the bookmark on an opportunity to keep it here." />
        ) : (
          opportunities.map((o) => (
            <button key={o.id} className="pill-row" onClick={() => s.openOpp(o.id)}>
              <span className="score-dot" aria-hidden="true">
                {o.window_passed ? '—' : Math.round(o.score_today)}
              </span>
              <span className="pill-row-main">
                <strong>{o.name}</strong>
                <small>
                  {o.tag}
                  {o.window_passed ? ' · window passed' : ` · ${Math.round(o.score_today)}/10 today`}
                  {o.score_when_saved !== null && o.score_when_saved !== undefined ? ` · ${Math.round(o.score_when_saved)} when saved` : ''}
                </small>
              </span>
              <Icon name="chevronRight" size={18} strokeWidth={2} />
            </button>
          ))
        )}
      </div>
    </section>
  );
}

function Empty({ icon, text }: { icon: 'film' | 'bookmark'; text: string }) {
  return (
    <div className="empty-block">
      <span className="circle white" aria-hidden="true">
        <Icon name={icon} size={20} strokeWidth={2} />
      </span>
      <p>{text}</p>
    </div>
  );
}
