'use client';
/**
 * A Follower Persona's avatar (v2.2 §2, v2.3): a glowing purple orb with a soft cluster of dots
 * inside that breathes and reacts. The dots come from the persona's seed (lib/avatar.ts, the
 * same algorithm as the share card), so a persona looks the same everywhere. A mood only moves,
 * scales or dims the dots.
 * Reduced motion (or animated={false}) shows the static mood shapes.
 */
import { useId, useMemo, useSyncExternalStore } from 'react';

import { dots, ORB, ORB_R, place, type Mood, type PersonaColor } from '@/lib/avatar';

export type AvatarState = 'idle' | 'listening' | 'thinking' | 'loading';

const REDUCE = '(prefers-reduced-motion: reduce)';

function subscribe(onChange: () => void) {
  if (typeof window === 'undefined' || !window.matchMedia) return () => {};
  const mq = window.matchMedia(REDUCE);
  mq.addEventListener?.('change', onChange);
  return () => mq.removeEventListener?.('change', onChange);
}

/** True when the viewer asked for less motion. */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia(REDUCE).matches : false),
    () => false,
  );
}

/** "The Festive Planner, 31% of your comments, mood: love" */
export function avatarLabel(name: string, share: number | null | undefined, mood: Mood): string {
  const pct = share === null || share === undefined ? null : Math.round(share * 100);
  return [name, pct === null ? null : `${pct}% of your comments`, `mood: ${mood}`].filter(Boolean).join(', ');
}

export function PersonaAvatar({
  seed,
  color,
  mood = 'neutral',
  size = 64,
  animated = true,
  state = 'idle',
  name,
  share,
  label,
  decorative = false,
}: {
  seed: number;
  color: PersonaColor;
  mood?: Mood;
  size?: 24 | 40 | 64 | 120 | number;
  animated?: boolean;
  state?: AvatarState;
  name?: string;
  share?: number | null;
  label?: string;
  decorative?: boolean;
}) {
  const reduced = useReducedMotion();
  const base = useMemo(() => dots(seed), [seed]);
  const shown: Mood = state === 'listening' || state === 'loading' ? 'listening' : state === 'thinking' ? 'thinking' : mood;
  const [hi, mid, edge, dot] = ORB[state === 'loading' ? 'gray' : color];
  const gradient = `orb-${useId().replace(/[^a-zA-Z0-9]/g, '')}`;
  const moving = animated && !reduced;
  const aria = label ?? (name ? avatarLabel(name, share, shown) : `Follower persona, mood: ${shown}`);
  return (
    <svg
      className={`pa ${moving ? 'pa-moving' : 'pa-static'}`}
      width={size}
      height={size}
      viewBox="0 0 100 100"
      data-mood={shown}
      data-static={moving ? undefined : 'true'}
      {...(decorative ? { 'aria-hidden': true } : { role: 'img', 'aria-label': aria })}
    >
      <defs>
        <radialGradient id={gradient} cx="0.34" cy="0.28" r="0.82">
          <stop offset="0" stopColor={hi} />
          <stop offset="0.55" stopColor={mid} />
          <stop offset="1" stopColor={edge} />
        </radialGradient>
      </defs>
      <circle className="pa-orb" cx={50} cy={50} r={ORB_R} fill={`url(#${gradient})`} />
      {/* The dots stay mounted so they spring between moods; the group's class carries the
          looping motion (and love's one pulse, which replays whenever the class returns). */}
      <g className={`pa-g pa-${shown}${moving ? ' pa-anim' : ''}`}>
        {base.map((d, i) => {
          const p = place(d, shown);
          return (
            <circle
              key={i}
              className="pa-dot"
              cx={d.x}
              cy={d.y}
              r={p.r}
              fill={dot}
              style={{
                transform: `translate(${(p.x - d.x).toFixed(2)}px, ${(p.y - d.y).toFixed(2)}px)`,
                opacity: Math.round((0.45 + 0.55 * p.opacity) * 100) / 100,
                transitionDelay: moving ? `${(i % 12) * 14}ms` : undefined,
              }}
            />
          );
        })}
      </g>
    </svg>
  );
}

/** Breathing pale orbs while personas are being built. */
export function AvatarSkeleton({ size = 64, seed = 1 }: { size?: number; seed?: number }) {
  return <PersonaAvatar seed={seed} color="gray" state="loading" size={size} label="Building your follower personas" />;
}
