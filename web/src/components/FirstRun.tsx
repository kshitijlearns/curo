'use client';
/** First-run pieces (v2.1): the live progress strip and the onboarding illustrations. */
import { Icon } from './Icon';
import { PersonaAvatar } from './PersonaAvatar';
import type { S } from '@/lib/api';

/** What the backend is doing right now, from the onboarding job and the recap. */
export function progressText(st: S['OnboardingStatus'] | undefined): { text: string; done: boolean } {
  if (!st || st.status === 'not_started') return { text: 'Getting started…', done: false };
  if (st.status === 'failed') return { text: st.error || 'Something went wrong reading that account.', done: true };
  if (st.step === 'recap_ready' || st.recap_status === 'ready') return { text: 'Your recap is ready ✓', done: true };
  if (st.step === 'recap' || st.recap_status === 'building') return { text: 'Building your recap…', done: false };
  if (st.step === 'comments' || st.comments_total) {
    return { text: st.reels_found ? `Found ${st.reels_found} reels · reading what your audience says…` : 'Reading what your audience says…', done: false };
  }
  if (st.step === 'reels') return { text: 'Collecting your reels…', done: false };
  return { text: 'Reading your profile…', done: false };
}

export function ProgressStrip({ status }: { status: S['OnboardingStatus'] | undefined }) {
  const p = progressText(status);
  return (
    <div className={`progress-strip${p.done ? ' done' : ''}`} role="status" aria-live="polite">
      <span className="dot" aria-hidden="true" />
      <span>{p.text}</span>
    </div>
  );
}

// The first-run art (v2.3): the same glowing orbs the app is built around.
const CREW = [
  { seed: 20271, color: 'blue', size: 118, x: 50, y: 48 },
  { seed: 41203, color: 'lavender', size: 76, x: 16, y: 70 },
  { seed: 7719, color: 'pink', size: 66, x: 84, y: 64 },
  { seed: 93311, color: 'ink', size: 48, x: 30, y: 16 },
] as const;

/** Card 1 and the first screen: four followers floating on a curve. */
export function ArtHome() {
  return (
    <div className="orb-stage" style={{ width: '100%', height: '100%' }} role="img" aria-label="Your four follower groups">
      <svg className="curve" viewBox="0 0 400 196" preserveAspectRatio="none" aria-hidden="true">
        <path d="M-6 150 C 70 96, 120 40, 200 84 S 330 150, 410 92" fill="none" stroke="#7B5CFA" strokeOpacity={0.45} strokeWidth={1.5} strokeDasharray="2 7" strokeLinecap="round" />
      </svg>
      {CREW.map((c) => (
        <div key={c.seed} className="orb" style={{ left: `${c.x}%`, top: `${c.y}%` }}>
          <PersonaAvatar seed={c.seed} color={c.color} mood="like" size={c.size} decorative />
        </div>
      ))}
    </div>
  );
}

/** Card 2, Idea Studio: an idea turning into a script, a storyboard and a caption. */
export function ArtStudio() {
  const steps = ['Idea', 'Script', 'Storyboard', 'Caption'];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }} role="img" aria-label="An idea becoming a script, storyboard and caption">
      <span className="circle violet" style={{ width: 92, height: 92, boxShadow: 'var(--shadow-lift)' }}>
        <Icon name="sparkle" size={42} color="#FFFFFF" />
      </span>
      <div className="chip-row" style={{ justifyContent: 'center', color: 'var(--violet-deep)' }}>
        {steps.map((t) => (
          <span key={t} style={{ background: 'rgba(255,255,255,0.8)', boxShadow: 'var(--shadow-soft)' }}>
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Card 3, Simulator: a reel playing to a crowd of small AI followers. */
export function ArtSimulator() {
  const dots = [];
  for (let r = 0; r < 4; r++) {
    for (let c = 0; c < 11; c++) {
      const on = (r * 11 + c) % 3 !== 0;
      dots.push(<circle key={`${r}-${c}`} cx={20 + c * 26} cy={136 + r * 16} r={5.5} fill={on ? '#7B5CFA' : '#CFC2FF'} />);
    }
  }
  return (
    <svg viewBox="0 0 300 200" width="100%" height="100%" role="img" aria-label="A reel watched by AI followers">
      <defs>
        <linearGradient id="reel" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#4B2FD1" />
          <stop offset="1" stopColor="#7B5CFA" />
        </linearGradient>
      </defs>
      <rect x="116" y="8" width="68" height="110" rx="16" fill="url(#reel)" />
      <path d="M142 44 v34 l27 -17 z" fill="#FFFFFF" />
      <path d="M204 26 c 20 -6 34 4 36 18 c 2 14 -12 22 -26 20 l -10 10 l 2 -12 c -14 -8 -14 -30 -2 -36z" fill="#FFFFFF" />
      <text x="222" y="50" textAnchor="middle" fontSize="12" fontWeight="600" fill="#141414">
        why?
      </text>
      {dots}
    </svg>
  );
}
