'use client';
/**
 * Home (v2.1 §5): one scroll, four swipeable sections —
 * 1. Insights: your Creator Recap (cover, highlight stats, all recaps)
 * 2. Opportunity areas
 * 3. Trending for you (tap → detail with "Make this my way")
 * 4. What your followers will love
 * Each section loads on its own: a skeleton while loading, a retry card if it fails.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { Section } from '@/components/Carousel';
import { ProgressStrip } from '@/components/FirstRun';
import { Icon } from '@/components/Icon';
import { Overlay } from '@/components/Overlay';
import { ScoreRing } from '@/components/ScoreRing';
import { api, type S } from '@/lib/api';
import {
  useFollowerIdeas,
  useLatestRecap,
  useMe,
  useOnboardingStatus,
  useOpportunities,
  useTrends,
} from '@/lib/hooks';
import { LATER_KEY } from '@/lib/session';
import { useApp } from '@/state/app';

function Skeletons({ n = 2 }: { n?: number }) {
  return (
    <div className="carousel" aria-hidden="true">
      {Array.from({ length: n }, (_, i) => (
        <div key={i} className="skeleton" />
      ))}
    </div>
  );
}

function useStartProject() {
  const s = useApp();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (idea: string) => api<S['ProjectStarted']>('/projects', { body: { idea_text: idea } }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['me'] });
      s.openProject(r.project_id);
    },
  });
}

export function HomeView() {
  const me = useMe();
  const qc = useQueryClient();
  const s = useApp();
  const [remind, setRemind] = useState(false);

  useEffect(() => {
    if (!me.data?.is_anonymous) return setRemind(false);
    try {
      // "Maybe later" this visit: remind on the next one.
      setRemind(sessionStorage.getItem(LATER_KEY) !== '1');
    } catch {
      setRemind(true);
    }
  }, [me.data?.is_anonymous]);

  const name = me.data?.account?.username;
  return (
    <>
      <div className="row between" style={{ margin: '0 4px 4px' }}>
        <p className="light" style={{ margin: 0, fontSize: 16 }}>
          {name ? `Hi @${name}` : 'Hi'}
        </p>
        <button
          className="pill"
          onClick={() => {
            // Re-fetches the sections only; never starts a new scrape.
            qc.invalidateQueries();
            s.showToast('Refreshed.');
          }}
        >
          <Icon name="refresh" size={16} /> Refresh
        </button>
      </div>
      {remind ? (
        <div className="card lav" role="note" style={{ marginTop: 12 }}>
          <h3 style={{ fontSize: 17 }}>Save your account</h3>
          <p className="light">Keep your recaps and get a new one every month. Unsaved accounts are deleted after 30 days.</p>
          <div className="row" style={{ marginTop: 12 }}>
            <Link href="/save" className="btn small">
              Save with email
            </Link>
            <button className="btn small ghost" onClick={() => setRemind(false)}>
              Later
            </button>
          </div>
        </div>
      ) : null}
      <RecapSection />
      <OpportunitySection />
      <TrendSection />
      <FollowerSection />
    </>
  );
}

// ---------------------------------------------------------------------- 1. Creator Recap

function RecapSection() {
  const router = useRouter();
  const q = useLatestRecap();
  const r = q.data;
  const building = q.isSuccess && (!r || r.status === 'building');
  const status = useOnboardingStatus(building);
  if (q.isLoading) {
    return (
      <Section title="Your Creator Recap">
        <div className="skeleton" />
      </Section>
    );
  }
  if (q.error) return <Section title="Your Creator Recap" error={q.error} onRetry={() => q.refetch()}>{null}</Section>;
  if (!r || r.status !== 'ready') {
    return (
      <Section title="Your Creator Recap">
        <div className="card gray" style={{ minHeight: 150 }}>
          <h3>Your recap is on its way</h3>
          <p className="light" style={{ marginBottom: 12 }}>
            It fills in here as soon as it’s ready.
          </p>
          <ProgressStrip status={status.data} />
        </div>
      </Section>
    );
  }
  const headline = (r.stats ?? [])[0];
  const open = (slide?: string) => {
    const i = slide ? (r.slides ?? []).findIndex((s) => s.slide_id === slide) : 0;
    router.push(`/recap?id=${r.id}${i > 0 ? `&slide=${i}` : ''}`);
  };
  return (
    <Section title="Your Creator Recap" label="Insights: your Creator Recap">
      <button className="card tap lav" onClick={() => open()} style={{ minHeight: 190 }} aria-label={`Play your recap: ${r.period_label}`}>
        <div className="row between">
          <span className="pill white">{r.period_label}</span>
          {r.is_new ? <span className="new-badge">New</span> : <Icon name="play" size={18} />}
        </div>
        <h3 style={{ marginTop: 14, fontSize: 22 }}>{r.creator_level ?? 'Your recap'}</h3>
        <p style={{ fontWeight: 600 }}>{r.archetype}</p>
        {headline ? (
          <p style={{ marginTop: 12 }}>
            <span className="score" style={{ fontSize: 34, color: 'var(--blue)' }}>
              {headline.value}
            </span>{' '}
            <span className="light">{headline.label}</span>
          </p>
        ) : null}
      </button>
      {(r.stats ?? []).slice(0, 4).map((st) => (
        <button key={st.slide} className="card tap narrow" onClick={() => open(st.slide)} aria-label={`${st.value} ${st.label}: open this slide`}>
          <span className="score" style={{ fontSize: 30 }}>
            {st.value}
          </span>
          <p className="light small" style={{ marginTop: 8 }}>
            {st.label}
          </p>
        </button>
      ))}
      <Link href="/recaps" className="card tap narrow gray" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
        <h3 style={{ fontSize: 17 }}>All recaps</h3>
        <span className="row small" style={{ fontWeight: 600 }}>
          See them <Icon name="arrowRight" size={16} />
        </span>
      </Link>
    </Section>
  );
}

// ---------------------------------------------------------------------- 2. Opportunity areas

function OpportunitySection() {
  const s = useApp();
  const q = useOpportunities();
  if (q.isLoading) return <Section title="Opportunity areas"><Skeletons /></Section>;
  if (q.error) return <Section title="Opportunity areas" error={q.error} onRetry={() => q.refetch()}>{null}</Section>;
  const cards = (q.data ?? []).slice(0, 5);
  return (
    <Section title="Opportunity areas">
      {cards.length === 0 ? (
        <div className="card gray">
          <p className="light">Opportunity areas appear after CURO’s first nightly run on your reels.</p>
        </div>
      ) : (
        cards.map((o) => (
          <button key={o.id} className="card tap" onClick={() => s.openOpp(o.id)}>
            <div className="row" style={{ gap: 14, alignItems: 'flex-start' }}>
              <ScoreRing value={o.score_shown} max={10} size={64} label="Opportunity score" />
              <div style={{ minWidth: 0 }}>
                <span className="pill lav">{o.tag}</span>
                <h3 style={{ marginTop: 8 }}>{o.name}</h3>
              </div>
            </div>
            <p className="light" style={{ marginTop: 8 }}>
              {o.card}
            </p>
          </button>
        ))
      )}
    </Section>
  );
}

// ---------------------------------------------------------------------- 3. Trending for you

function TrendSection() {
  const q = useTrends();
  const [open, setOpen] = useState<S['TrendCard'] | null>(null);
  if (q.isLoading) return <Section title="Trending for you"><Skeletons /></Section>;
  if (q.error) return <Section title="Trending for you" error={q.error} onRetry={() => q.refetch()}>{null}</Section>;
  const cards = q.data ?? [];
  return (
    <>
      <Section title="Trending for you">
        {cards.length === 0 ? (
          <div className="card gray">
            <p className="light">Nothing new is picking up in your niche today. Check back tomorrow.</p>
          </div>
        ) : (
          cards.map((t) => (
            <button key={t.id} className="card tap" onClick={() => setOpen(t)}>
              <div className="row between">
                <span className="pill pink">{t.saturation === 'unknown' ? 'New' : `${t.saturation} competition`}</span>
                {t.window_end ? <span className="small muted">until {fmtDate(t.window_end)}</span> : null}
              </div>
              <h3 style={{ marginTop: 10 }}>{t.name}</h3>
              <p className="light small">{t.why_rising}</p>
              {(t.example_angles ?? []).slice(0, 2).map((a) => (
                <p key={a} className="small" style={{ marginTop: 6 }}>
                  → {a}
                </p>
              ))}
            </button>
          ))
        )}
      </Section>
      {open ? <TrendSheet t={open} onClose={() => setOpen(null)} /> : null}
    </>
  );
}

function TrendSheet({ t, onClose }: { t: S['TrendCard']; onClose: () => void }) {
  const start = useStartProject();
  return (
    <Overlay labelledBy="trend-title" onClose={onClose}>
      <div className="row between">
        <span className="pill pink">{t.saturation === 'unknown' ? 'New' : `${t.saturation} competition`}</span>
        <button className="circle sm" onClick={onClose} aria-label="Close">
          <Icon name="close" size={18} />
        </button>
      </div>
      <h2 id="trend-title" style={{ fontSize: 22, margin: '14px 0 6px' }}>
        {t.name}
      </h2>
      <p className="light">{t.summary}</p>
      <p style={{ marginTop: 10 }}>{t.why_rising}</p>
      <p className="small muted" style={{ marginTop: 6 }}>
        {t.why_it_fits}
      </p>
      {t.window_start || t.window_end ? (
        <p className="small" style={{ marginTop: 6 }}>
          Timing: {t.window_start ? fmtDate(t.window_start) : 'now'} – {t.window_end ? fmtDate(t.window_end) : 'ongoing'}
        </p>
      ) : null}
      <h3 style={{ fontSize: 16, marginTop: 16 }}>Make this my way</h3>
      <div className="stack">
        {(t.example_angles ?? []).map((a) => (
          <button key={a} className="card tap" style={{ margin: 0 }} disabled={start.isPending} onClick={() => start.mutate(`${a} (trend: ${t.name})`)}>
            <div className="row between">
              <span>{a}</span>
              <Icon name="arrowRight" size={18} />
            </div>
          </button>
        ))}
      </div>
      {(t.hashtags ?? []).length ? (
        <p className="small muted" style={{ marginTop: 12 }}>
          {(t.hashtags ?? []).slice(0, 5).map((h) => `#${h}`).join(' ')}
        </p>
      ) : null}
    </Overlay>
  );
}

// ---------------------------------------------------------------------- 4. What your followers will love

function FollowerSection() {
  const q = useFollowerIdeas();
  const start = useStartProject();
  if (q.isLoading) return <Section title="What your followers will love"><Skeletons /></Section>;
  if (q.error) return <Section title="What your followers will love" error={q.error} onRetry={() => q.refetch()}>{null}</Section>;
  const ideas = q.data ?? [];
  return (
    <Section title="What your followers will love">
      {ideas.length === 0 ? (
        <div className="card gray">
          <p className="light">Ideas from your audience appear once CURO has read your comments.</p>
        </div>
      ) : (
        ideas.map((i) => (
          <article key={i.id} className="card">
            {i.segment ? <span className="pill lav">For {i.segment.toLowerCase()}</span> : null}
            <h3 style={{ marginTop: 10 }}>{i.title}</h3>
            <p className="light small">{i.why}</p>
            <button className="btn small" style={{ marginTop: 12 }} disabled={start.isPending} onClick={() => start.mutate(i.title)}>
              <Icon name="studio" size={16} /> Open in Studio
            </button>
          </article>
        ))
      )}
    </Section>
  );
}

export function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}
