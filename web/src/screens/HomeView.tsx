'use client';
/**
 * Home (v3): one scroll of colour blocks, light on words.
 * 1. A big greeting, and two action tiles (make a reel, test one)
 * 2. Your followers: the four personas on a podium, ranked on a dark card (tap → detail sheet)
 * 3. They want more of: each persona's asks, one tap starts a Studio project
 * 4. Your Creator Recap: a dark card with four big numbers
 * 5. Opportunity areas: a stacked deck of coloured cards, best first
 * 6. Trending for you: a swipeable row (tap → detail with "Make this my way")
 * Each section loads on its own: a skeleton while loading, a retry card if it fails.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { Carousel } from '@/components/Carousel';
import { Arrow, Chip, TopBar } from '@/components/Chrome';
import { ProgressStrip } from '@/components/FirstRun';
import { Icon } from '@/components/Icon';
import { Overlay } from '@/components/Overlay';
import { PersonaPodium, SectionHead, WantsPanel } from '@/components/Personas';
import { api, type S } from '@/lib/api';
import { useLatestRecap, useMe, useOnboardingStatus, useOpportunities, useTrends } from '@/lib/hooks';
import { blockAt } from '@/lib/palette';
import { LATER_KEY } from '@/lib/session';
import { useApp } from '@/state/app';

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

function SectionError({ title, onRetry }: { title: string; onRetry: () => void }) {
  return (
    <section aria-label={title}>
      <SectionHead title={title} />
      <div className="card coral" role="alert">
        <p>This section didn’t load.</p>
        <button className="btn small" style={{ marginTop: 10 }} onClick={onRetry}>
          Try again
        </button>
      </div>
    </section>
  );
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

  const first = me.data?.account?.full_name?.split(' ')[0] || me.data?.account?.username;
  const hour = new Date().getHours();
  const part = hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : 'evening';
  return (
    <>
      <TopBar
        right={
          <button
            className="circle"
            aria-label="Refresh"
            onClick={() => {
              // Re-fetches the sections only; never starts a new scrape.
              qc.invalidateQueries();
              s.showToast('Refreshed.');
            }}
          >
            <Icon name="refresh" size={18} strokeWidth={2} />
          </button>
        }
      />
      <div className="hero">
        <span className="eyebrow">{new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'short' })}</span>
        <h1 className="display-title">
          Good {part}
          {first ? (
            <>
              ,<br />
              <span className="hl">{first}</span>
            </>
          ) : null}
        </h1>
      </div>

      <div className="tiles">
        <button className="tile blk-lemon" onClick={() => s.nav('studio')}>
          <span className="tile-icon">
            <Icon name="sparkle" size={18} />
          </span>
          <strong>
            Make a<br />
            new reel
          </strong>
          <Arrow dark />
        </button>
        <button className="tile blk-coral" onClick={() => s.nav('sim')}>
          <span className="tile-icon">
            <Icon name="simulator" size={18} strokeWidth={2} />
          </span>
          <strong>
            Test before
            <br />
            you post
          </strong>
          <Arrow dark />
        </button>
      </div>

      {remind ? (
        <div className="banner blk-lime" role="note">
          <span className="circle sm white" aria-hidden="true">
            <Icon name="bookmark" size={16} strokeWidth={2} />
          </span>
          <span className="banner-main">
            <strong>Save your account</strong>
            <small>Unsaved accounts go after 30 days.</small>
          </span>
          <Link href="/save" className="btn small ink">
            Save
          </Link>
          <button className="circle sm clear" onClick={() => setRemind(false)} aria-label="Later">
            <Icon name="close" size={16} strokeWidth={2} />
          </button>
        </div>
      ) : null}

      <PersonaPodium />
      <WantsPanel />
      <RecapSection />
      <OpportunitySection />
      <TrendSection />
    </>
  );
}

// ---------------------------------------------------------------------- Creator Recap

const STAT_BLOCKS = ['lime', 'lemon', 'pink', 'sky'] as const;

function RecapSection() {
  const router = useRouter();
  const q = useLatestRecap();
  const r = q.data;
  const building = q.isSuccess && (!r || r.status === 'building');
  const status = useOnboardingStatus(building);
  const title = 'Your Creator Recap';
  if (q.isLoading) {
    return (
      <section aria-label={title}>
        <SectionHead title={title} />
        <div className="skeleton tall" />
      </section>
    );
  }
  if (q.error) return <SectionError title={title} onRetry={() => q.refetch()} />;
  if (!r || r.status !== 'ready') {
    return (
      <section aria-label={title}>
        <SectionHead title={title} />
        <div className="recap-card">
          <Chip tone="clear">On its way</Chip>
          <h3 className="recap-title">Your recap is being made</h3>
          <ProgressStrip status={status.data} />
        </div>
      </section>
    );
  }
  const open = (slide?: string) => {
    const i = slide ? (r.slides ?? []).findIndex((x) => x.slide_id === slide) : 0;
    router.push(`/recap?id=${r.id}${i > 0 ? `&slide=${i}` : ''}`);
  };
  return (
    <section aria-label="Insights: your Creator Recap">
      <SectionHead
        title={title}
        action={
          <Link href="/recaps" className="see-all">
            All recaps
          </Link>
        }
      />
      <div className="recap-card">
        <button className="recap-top" onClick={() => open()} aria-label={`Play your recap: ${r.period_label}`}>
          <div className="row between">
            <Chip tone="clear">{r.period_label}</Chip>
            {r.is_new ? <span className="new-badge">New</span> : null}
          </div>
          {r.creator_level ? <span className="recap-level">{r.creator_level}</span> : null}
          <h3 className="recap-title">{r.archetype ?? 'Your recap'}</h3>
          <span className="play-pill">
            <Icon name="play" size={14} /> Play
          </span>
        </button>
        <div className="stat-grid">
          {(r.stats ?? []).slice(0, 4).map((st, i) => (
            <button key={st.slide} className={`stat-tile blk-${STAT_BLOCKS[i % 4]}`} onClick={() => open(st.slide)} aria-label={`${st.value} ${st.label}: open this slide`}>
              <b>{st.value}</b>
              <span>{st.label}</span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------- Opportunity areas

function OpportunitySection() {
  const s = useApp();
  const q = useOpportunities();
  const [all, setAll] = useState(false);
  const title = 'Opportunity areas';
  if (q.isLoading) {
    return (
      <section aria-label={title}>
        <SectionHead title={title} />
        <div className="skeleton tall" />
      </section>
    );
  }
  if (q.error) return <SectionError title={title} onRetry={() => q.refetch()} />;
  const list = q.data ?? [];
  const cards = all ? list : list.slice(0, 4);
  return (
    <section aria-label={title}>
      <SectionHead
        title={title}
        action={
          list.length > 4 ? (
            <button className="see-all" onClick={() => setAll((v) => !v)} aria-expanded={all}>
              {all ? 'Show less' : `See all ${list.length}`}
            </button>
          ) : undefined
        }
      />
      {cards.length === 0 ? (
        <div className="card paper">
          <p className="light">Opportunity areas appear after CURO’s first nightly run on your reels.</p>
        </div>
      ) : (
        <div className="deck">
          {cards.map((o, i) => (
            <button key={o.id} className={`deck-card blk-${blockAt(i)}${i === 0 ? ' lead' : ''}`} style={{ zIndex: cards.length - i }} onClick={() => s.openOpp(o.id)} aria-label={`${o.name}, scores ${o.score_shown} of 10: open`}>
              <div className="row between">
                <Chip>{o.tag}</Chip>
                <span className="deck-score" aria-hidden="true">
                  {o.score_shown}
                  <small>/10</small>
                </span>
              </div>
              <div className="row between" style={{ alignItems: 'flex-end', gap: 12 }}>
                <h3 className="deck-title">{o.name}</h3>
                <Arrow />
              </div>
              {i === 0 ? <p className="deck-text">{o.card}</p> : null}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------- Trending for you

const TREND_BLOCKS = ['sky', 'lime', 'pink', 'lemon', 'violet'] as const;

function TrendSection() {
  const q = useTrends();
  const [open, setOpen] = useState<{ t: S['TrendCard']; i: number } | null>(null);
  const title = 'Trending for you';
  if (q.isLoading) {
    return (
      <section aria-label={title}>
        <SectionHead title={title} />
        <div className="skeleton tall" />
      </section>
    );
  }
  if (q.error) return <SectionError title={title} onRetry={() => q.refetch()} />;
  const cards = q.data ?? [];
  return (
    <section aria-label={title}>
      <SectionHead title={title} hint={cards.length ? `${cards.length} picking up` : undefined} />
      {cards.length === 0 ? (
        <div className="card paper">
          <p className="light">Nothing new is picking up in your niche today. Check back tomorrow.</p>
        </div>
      ) : (
        <Carousel label={title}>
          {cards.map((t, i) => (
            <button key={t.id} className={`trend-card blk-${TREND_BLOCKS[i % TREND_BLOCKS.length]}`} onClick={() => setOpen({ t, i })}>
              <div className="row between">
                <Chip>
                  <Icon name="trend" size={14} strokeWidth={2.2} /> {saturation(t.saturation)}
                </Chip>
                {t.window_end ? <span className="trend-until">until {fmtDate(t.window_end)}</span> : null}
              </div>
              <h3 className="trend-title">{t.name}</h3>
              <p className="trend-why">{t.why_rising}</p>
              <div className="row between" style={{ marginTop: 'auto' }}>
                <span className="trend-angles">{(t.example_angles ?? []).length} ways to make it</span>
                <Arrow dark />
              </div>
            </button>
          ))}
        </Carousel>
      )}
      {open ? <TrendSheet t={open.t} block={TREND_BLOCKS[open.i % TREND_BLOCKS.length]} onClose={() => setOpen(null)} /> : null}
    </section>
  );
}

const saturation = (x: string) => (x === 'unknown' ? 'New' : `${x[0].toUpperCase()}${x.slice(1)} competition`);

function TrendSheet({ t, block, onClose }: { t: S['TrendCard']; block: string; onClose: () => void }) {
  const start = useStartProject();
  return (
    <Overlay labelledBy="trend-title" onClose={onClose}>
      <div className={`sheet-hero blk-${block}`}>
        <div className="row between">
          <Chip>
            <Icon name="trend" size={14} strokeWidth={2.2} /> {saturation(t.saturation)}
          </Chip>
          <button className="circle white" onClick={onClose} aria-label="Close">
            <Icon name="close" size={18} />
          </button>
        </div>
        <h2 id="trend-title" className="block-title">
          {t.name}
        </h2>
        <p style={{ margin: 0 }}>{t.summary}</p>
        {t.window_start || t.window_end ? (
          <div className="row" style={{ gap: 6, marginTop: 12 }}>
            <Chip>
              <Icon name="clock" size={14} strokeWidth={2} /> {t.window_start ? fmtDate(t.window_start) : 'Now'} – {t.window_end ? fmtDate(t.window_end) : 'ongoing'}
            </Chip>
          </div>
        ) : null}
      </div>
      <div className="fact-rows">
        <div className="fact">
          <span className="fact-icon blk-lemon">
            <Icon name="bolt" size={16} strokeWidth={2} />
          </span>
          <p>{t.why_rising}</p>
        </div>
        <div className="fact">
          <span className="fact-icon blk-lime">
            <Icon name="check" size={16} strokeWidth={2.4} />
          </span>
          <p>{t.why_it_fits}</p>
        </div>
      </div>
      <h3 className="sheet-label">Make this my way</h3>
      <div className="stack" style={{ gap: 8 }}>
        {(t.example_angles ?? []).map((a) => (
          <button key={a} className="pill-row bordered" disabled={start.isPending} onClick={() => start.mutate(`${a} (trend: ${t.name})`)}>
            <span className="pill-row-main">
              <strong>{a}</strong>
            </span>
            <span className="arrow dark" aria-hidden="true">
              <Icon name="arrowUpRight" size={18} strokeWidth={2.2} />
            </span>
          </button>
        ))}
      </div>
      {(t.hashtags ?? []).length ? (
        <div className="row wrap" style={{ gap: 6, marginTop: 14 }}>
          {(t.hashtags ?? []).slice(0, 5).map((h) => (
            <span key={h} className="chip outline">
              #{h}
            </span>
          ))}
        </div>
      ) : null}
    </Overlay>
  );
}

export function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}
