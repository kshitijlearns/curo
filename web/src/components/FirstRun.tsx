'use client';
/** First-run pieces (v2.1): the live progress strip and the onboarding illustrations. */
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

const stroke = { stroke: '#242424', strokeWidth: 2.4, strokeLinecap: 'round', strokeLinejoin: 'round' } as const;
const line = { ...stroke, fill: 'none' } as const;

/** Card 1 — Home: a phone with a recap cover and swipeable cards. */
export function ArtHome() {
  return (
    <svg viewBox="0 0 300 200" width="100%" height="100%" role="img" aria-label="A phone showing your recap and cards">
      <rect x="95" y="14" width="110" height="176" rx="18" fill="#FFFFFF" {...stroke} />
      <rect x="107" y="34" width="86" height="64" rx="12" fill="#C3BFF2" />
      <text x="150" y="62" textAnchor="middle" fontSize="11" fontWeight="600" fill="#242424">Your month</text>
      <text x="150" y="84" textAnchor="middle" fontSize="18" fontWeight="600" fill="#5B73F2">2.4L</text>
      <rect x="107" y="108" width="54" height="40" rx="10" fill="#F2D4E2" />
      <rect x="167" y="108" width="40" height="40" rx="10" fill="#E4E4EC" />
      <rect x="107" y="156" width="86" height="20" rx="10" fill="#E4E4EC" />
      <path d="M40 150 C 60 120, 70 90, 88 70" {...line} />
      <path d="M78 66 L 90 68 L 86 80" {...line} />
      <circle cx="245" cy="60" r="18" fill="#F2D4E2" />
      <path d="M238 60 l5 5 l10 -11" {...line} />
    </svg>
  );
}

/** Card 2 — Idea Studio: a lightbulb over a script and storyboard frames. */
export function ArtStudio() {
  return (
    <svg viewBox="0 0 300 200" width="100%" height="100%" role="img" aria-label="An idea becoming a script and storyboard">
      <path d="M150 22 a34 34 0 0 0 -20 61 v12 h40 v-12 a34 34 0 0 0 -20 -61z" fill="#F2D4E2" {...stroke} />
      <path d="M138 106 h24" {...line} />
      <rect x="40" y="128" width="66" height="54" rx="10" fill="#FFFFFF" {...stroke} />
      <path d="M52 144 h42 M52 156 h34 M52 168 h38" {...line} strokeWidth={2} />
      <rect x="117" y="128" width="66" height="54" rx="10" fill="#C3BFF2" {...stroke} />
      <circle cx="150" cy="150" r="10" fill="#FFFFFF" {...stroke} />
      <path d="M135 174 c8 -10 22 -10 30 0" {...line} strokeWidth={2} />
      <rect x="194" y="128" width="66" height="54" rx="10" fill="#FFFFFF" {...stroke} />
      <text x="227" y="160" textAnchor="middle" fontSize="12" fontWeight="600" fill="#5B73F2">#festive</text>
    </svg>
  );
}

/** Card 3 — Simulator: a reel playing to a crowd of small AI followers. */
export function ArtSimulator() {
  const dots = [];
  for (let r = 0; r < 4; r++) {
    for (let c = 0; c < 9; c++) {
      const on = (r * 9 + c) % 3 !== 0;
      dots.push(<circle key={`${r}-${c}`} cx={40 + c * 28} cy={128 + r * 16} r={5} fill={on ? '#5B73F2' : '#E4E4EC'} />);
    }
  }
  return (
    <svg viewBox="0 0 300 200" width="100%" height="100%" role="img" aria-label="A reel watched by AI followers">
      <rect x="118" y="12" width="64" height="100" rx="12" fill="#C3BFF2" {...stroke} />
      <path d="M142 46 v30 l24 -15 z" fill="#242424" />
      <path d="M200 30 c 20 -6 34 4 36 18 c 2 14 -12 22 -26 20 l -10 10 l 2 -12" fill="#FFFFFF" {...stroke} />
      <text x="218" y="54" textAnchor="middle" fontSize="11" fontWeight="600" fill="#242424">why?</text>
      {dots}
    </svg>
  );
}
