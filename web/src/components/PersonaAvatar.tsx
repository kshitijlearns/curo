'use client';
/**
 * A Follower Persona's avatar (v2.2 §2): a soft cluster of dots that breathes and reacts.
 * The dots come from the persona's seed (lib/avatar.ts, the same algorithm as the share card),
 * so a persona looks the same everywhere. A mood only moves, scales or dims the dots.
 * Reduced motion (or animated={false}) shows the static mood shapes.
 */
import { useMemo, useSyncExternalStore } from 'react';

import { dots, HEX, LIGHT, place, RING, RING_R, type Mood, type PersonaColor } from '@/lib/avatar';

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

const lightOpacity = (o: number) => Math.round((0.6 + 0.4 * o) * 100) / 100;

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
  surface = 'light',
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
  surface?: 'light' | 'dark';
  decorative?: boolean;
}) {
  const reduced = useReducedMotion();
  const base = useMemo(() => dots(seed), [seed]);
  const shown: Mood = state === 'listening' || state === 'loading' ? 'listening' : state === 'thinking' ? 'thinking' : mood;
  const fill = state === 'loading' ? HEX.gray : HEX[color];
  const moving = animated && !reduced;
  const light = state === 'loading' || LIGHT.has(color);
  const ring = light;
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
      {surface === 'dark' && color === 'ink' ? <circle cx={50} cy={50} r={RING_R} fill="#FFFFFF" /> : null}
      {ring ? (
        <circle cx={50} cy={50} r={RING_R} fill="none" stroke={RING} strokeWidth={1} vectorEffect="non-scaling-stroke" />
      ) : null}
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
              fill={fill}
              style={{
                transform: `translate(${(p.x - d.x).toFixed(2)}px, ${(p.y - d.y).toFixed(2)}px)`,
                // Light dots are faint on white: their opacity range is lifted (still 40–100% depth).
                opacity: light ? lightOpacity(p.opacity) : p.opacity,
                transitionDelay: moving ? `${(i % 12) * 14}ms` : undefined,
              }}
            />
          );
        })}
      </g>
    </svg>
  );
}

/** Four breathing grey placeholders while personas are being built. */
export function AvatarSkeleton({ size = 64, seed = 1 }: { size?: number; seed?: number }) {
  return <PersonaAvatar seed={seed} color="gray" state="loading" size={size} label="Building your follower personas" />;
}
