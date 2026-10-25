// The Follower Persona avatar's dots (v2.2 §2). The same algorithm as
// api/curo/services/persona_avatar.py: one seeded generator (mulberry32), the same arithmetic,
// so a persona looks identical in the app and on the share card. Both copies are checked
// against avatar.fixture.json.

export type Mood = 'neutral' | 'love' | 'like' | 'unsure' | 'skip' | 'thinking' | 'listening';
export type PersonaColor = 'blue' | 'lavender' | 'pink' | 'ink' | 'gray';

export const MOODS: Mood[] = ['neutral', 'love', 'like', 'unsure', 'skip', 'thinking', 'listening'];
export const COLORS: PersonaColor[] = ['blue', 'lavender', 'pink', 'ink'];
export const HEX: Record<PersonaColor, string> = {
  blue: '#5B73F2',
  lavender: '#C3BFF2',
  pink: '#F2D4E2',
  ink: '#242424',
  gray: '#E4E4EC',
};
export const RING = '#E4E4EC';
export const LIGHT = new Set<PersonaColor>(['lavender', 'pink', 'gray']);

const GOLDEN = Math.PI * (3 - Math.sqrt(5));
export const CLUSTER_R = 31;
export const RING_R = 47;
const DOT_R = [2.7, 3.7, 4.7];
const MIN_DOTS = 18;
const MAX_DOTS = 40;

const round2 = (x: number) => Math.round(x * 100) / 100;

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a) >>> 0;
    t = (((t + (Math.imul(t ^ (t >>> 7), 61 | t) >>> 0)) >>> 0) ^ t) >>> 0;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export type Dot = { x: number; y: number; r: number; opacity: number };

export function dots(seed: number): Dot[] {
  const rand = mulberry32(seed);
  const n = MIN_DOTS + Math.floor(rand() * (MAX_DOTS - MIN_DOTS + 1));
  const turn = rand() * 2 * Math.PI;
  const out: Dot[] = [];
  for (let i = 0; i < n; i++) {
    const t = (i + 0.5) / n;
    const dist = CLUSTER_R * Math.sqrt(t) * (0.92 + 0.16 * rand());
    const angle = turn + i * GOLDEN + (rand() - 0.5) * 0.6;
    const u = rand();
    const size = u < 0.45 ? DOT_R[0] : u < 0.8 ? DOT_R[1] : DOT_R[2];
    const opacity = 0.4 + 0.6 * ((1 - t) * 0.6 + rand() * 0.4);
    out.push({
      x: round2(50 + dist * Math.cos(angle)),
      y: round2(50 + dist * Math.sin(angle)),
      r: size,
      opacity: round2(opacity),
    });
  }
  return out;
}

/** Where a dot sits in a mood: the static shape (what reduced motion shows). */
export function place(d: Dot, mood: Mood): Dot {
  let dx = 0;
  let dy = 0;
  let scale = 1;
  let fade = 1;
  const nx = (d.x - 50) / CLUSTER_R;
  if (mood === 'love') {
    dy = (d.y - 50) * -0.3 - 8 * Math.max(0, 1 - nx * nx) + 2;
  } else if (mood === 'like') {
    dy = -5;
    scale = 1.04;
  } else if (mood === 'unsure') {
    dx = (d.x - 50) * 0.25;
    dy = (d.y - 50) * 0.25;
    fade = 0.85;
  } else if (mood === 'skip') {
    dx = 12;
    dy = 3;
    scale = 0.85;
    fade = 0.45;
  } else if (mood === 'thinking') {
    const dist = Math.hypot(d.x - 50, d.y - 50) || 1;
    const target = 0.35 * dist + 0.65 * 24;
    dx = (d.x - 50) * (target / dist - 1);
    dy = (d.y - 50) * (target / dist - 1);
  } else if (mood === 'listening') {
    scale = 0.92;
  }
  return {
    x: round2(50 + (d.x + dx - 50) * scale),
    y: round2(50 + (d.y + dy - 50) * scale),
    r: round2(d.r * scale),
    opacity: round2(d.opacity * fade),
  };
}

export const colorForSlot = (slot: number): PersonaColor => COLORS[(slot - 1) % 4];
