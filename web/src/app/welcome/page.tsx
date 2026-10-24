'use client';
/**
 * Steps 2–3 of the first run (v2.1): three cards explaining CURO while the backend reads the
 * profile and builds the first recap, with a live progress strip; then a waiting screen if
 * the recap isn't ready (90 s → "we'll let you know", into Home; 5 min → a friendly fallback).
 */
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';

import { ArtHome, ArtSimulator, ArtStudio, ProgressStrip } from '@/components/FirstRun';
import { useOnboardingStatus } from '@/lib/hooks';
import { signedIn } from '@/lib/session';

const CARDS = [
  {
    title: 'Your Home: know what’s working',
    body: 'Every month you get a Creator Recap, a story of your content and your audience. Below it: opportunity areas, what’s trending in your niche, and ideas your followers will love.',
    art: <ArtHome />,
    bg: 'var(--lavender)',
  },
  {
    title: 'Idea Studio: create with CURO',
    body: 'Pick an opportunity or bring your own idea. CURO helps you shape it into a script, a shot-by-shot storyboard and a caption with hashtags, in your own style.',
    art: <ArtStudio />,
    bg: 'var(--pink)',
  },
  {
    title: 'Simulator: test before you post',
    body: 'Record your reel and upload it. 1,000 AI followers built from your real audience watch it, react, comment and skip. Then you can ask any of them why.',
    art: <ArtSimulator />,
    bg: 'var(--gray)',
  },
];
const TEASE_AFTER_MS = 90_000;
const GIVE_UP_MS = 5 * 60_000;

export default function Welcome() {
  const router = useRouter();
  const [i, setI] = useState(0);
  const [waiting, setWaiting] = useState(false);
  const started = useRef(Date.now());
  const swipe = useRef<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const status = useOnboardingStatus();
  const st = status.data;
  const ready = !!st?.recap_id && st.recap_status === 'ready';
  const failed = st?.status === 'failed';

  useEffect(() => {
    signedIn().then((ok) => !ok && router.replace('/start'));
  }, [router]);
  useEffect(() => {
    const t = window.setInterval(() => setElapsed(Date.now() - started.current), 1000);
    return () => window.clearInterval(t);
  }, []);
  useEffect(() => {
    if (elapsed > GIVE_UP_MS && !ready) {
      console.error('First recap not ready after 5 minutes', st);
    }
  }, [elapsed, ready, st]);
  useEffect(() => {
    if (waiting && ready && st?.recap_id) router.replace(`/recap?id=${st.recap_id}&first=1`);
  }, [waiting, ready, st?.recap_id, router]);

  const openRecap = () => {
    if (ready && st?.recap_id) router.push(`/recap?id=${st.recap_id}&first=1`);
    else setWaiting(true);
  };

  if (failed) {
    return (
      <div className="app">
        <header className="brand">
          <h1>Curo</h1>
        </header>
        <main className="sheet">
          <h2 className="section-title">We hit a snag</h2>
          <div className="card pink" role="alert">
            <p>{st?.error || 'We couldn’t read that account.'}</p>
          </div>
          <button className="btn block" onClick={() => router.replace('/start')}>
            Try another username
          </button>
        </main>
      </div>
    );
  }

  if (waiting) {
    const teasers = [
      st?.reels_found ? `You’ve posted ${st.reels_found} reels so far 👀` : 'Counting your reels…',
      st?.followers ? `${st.followers.toLocaleString('en-IN')} people follow you. Let’s see what they love.` : 'Reading your profile…',
      'Your recap ends with what type of creator you are.',
    ];
    const tease = teasers[Math.floor(elapsed / 4000) % teasers.length];
    return (
      <div className="onb" style={{ background: 'var(--ink)', color: 'var(--white)' }}>
        <main style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 24, padding: 28, maxWidth: 480, margin: '0 auto', width: '100%' }}>
          <div aria-hidden="true" style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
            {['var(--lavender)', 'var(--pink)', 'var(--blue)', 'var(--white)'].map((c, k) => (
              <span key={c} style={{ width: 22, height: 22, borderRadius: k % 2 ? 6 : 11, background: c, animation: `pulse 1.2s ${k * 0.15}s ease-in-out infinite` }} />
            ))}
          </div>
          <h1 style={{ margin: 0, fontSize: 30, textAlign: 'center' }}>Building your recap</h1>
          <p key={tease} style={{ margin: 0, textAlign: 'center', fontSize: 18, animation: 'rise 450ms var(--enter)' }}>
            {tease}
          </p>
          <div style={{ color: 'var(--ink)' }}>
            <ProgressStrip status={st} />
          </div>
          {elapsed > GIVE_UP_MS ? (
            <div className="card pink" style={{ color: 'var(--ink)' }}>
              <p>This is taking much longer than it should. Your Home is ready; the recap will appear there when it’s done.</p>
            </div>
          ) : null}
          {elapsed > TEASE_AFTER_MS ? (
            <button className="btn block lav" onClick={() => router.replace('/')}>
              We’ll let you know when it’s ready — go to Home
            </button>
          ) : null}
        </main>
      </div>
    );
  }

  const card = CARDS[i];
  const last = i === CARDS.length - 1;
  return (
    <div className="onb" style={{ background: card.bg }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '18px 20px', maxWidth: 480, margin: '0 auto', width: '100%' }}>
        <strong style={{ fontSize: 22 }}>Curo</strong>
        {!last ? (
          <button className="pill white" onClick={() => setI(CARDS.length - 1)}>
            Skip
          </button>
        ) : null}
      </div>
      <div style={{ maxWidth: 480, margin: '0 auto', width: '100%', flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div className="onb-art" aria-hidden="false" style={{ margin: '0 20px 20px' }}>
          {card.art}
        </div>
        <section
          className="onb-card"
          key={i}
          style={{ animation: 'rise 450ms var(--enter)', touchAction: 'pan-y' }}
          aria-roledescription="slide"
          aria-label={`${i + 1} of ${CARDS.length}`}
          onPointerDown={(e) => (swipe.current = e.clientX)}
          onPointerUp={(e) => {
            const from = swipe.current;
            swipe.current = null;
            if (from === null) return;
            const dx = e.clientX - from;
            if (dx < -60) setI((k) => Math.min(CARDS.length - 1, k + 1));
            if (dx > 60) setI((k) => Math.max(0, k - 1));
          }}
        >
          <div className="dots" style={{ justifyContent: 'flex-start', margin: 0 }}>
            {CARDS.map((_, k) => (
              <button key={k} aria-label={`Card ${k + 1}`} aria-current={k === i} onClick={() => setI(k)} />
            ))}
          </div>
          <h2>{card.title}</h2>
          <p>{card.body}</p>
          <div style={{ flex: 1 }} />
          <ProgressStrip status={st} />
          {last ? (
            <button className="btn block" style={{ height: 56, fontSize: 18 }} onClick={openRecap} aria-disabled={!ready}>
              {ready ? 'See my recap' : 'Almost there…'}
            </button>
          ) : (
            <button className="btn block" style={{ height: 56, fontSize: 18 }} onClick={() => setI(i + 1)}>
              Next
            </button>
          )}
        </section>
      </div>
    </div>
  );
}
