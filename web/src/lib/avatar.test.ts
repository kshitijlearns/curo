import { describe, expect, it } from 'vitest';

import { dots, MOODS, place } from './avatar';
import fixture from './avatar.fixture.json';

// The same fixture the Python copy (api/curo/services/persona_avatar.py) is tested against:
// both draw the same avatar from the same seed. Rounding may differ by one hundredth.
const close = (a: number[][], b: number[][]) =>
  a.length === b.length && a.every((row, i) => row.every((v, j) => Math.abs(v - b[i][j]) <= 0.011));

describe('persona avatar dots', () => {
  for (const [seed, want] of Object.entries((fixture as any).seeds as Record<string, any>)) {
    it(`seed ${seed} matches the Python algorithm in every mood`, () => {
      const ds = dots(Number(seed));
      expect(close(ds.map((d) => [d.x, d.y, d.r, d.opacity]), want.dots)).toBe(true);
      for (const m of MOODS) {
        expect(close(ds.map((d) => place(d, m)).map((p) => [p.x, p.y, p.r, p.opacity]), want.moods[m])).toBe(true);
      }
    });
  }

  it('draws 18–40 dots of three sizes with 40–100% opacity, the same every time', () => {
    for (const seed of [3, 77, 4242, 99991]) {
      const ds = dots(seed);
      expect(ds.length).toBeGreaterThanOrEqual(18);
      expect(ds.length).toBeLessThanOrEqual(40);
      expect(new Set(ds.map((d) => d.r)).size).toBeLessThanOrEqual(3);
      expect(ds.every((d) => d.opacity >= 0.4 && d.opacity <= 1)).toBe(true);
      expect(dots(seed)).toEqual(ds);
    }
  });

  it('gives every mood its own shape', () => {
    const ds = dots(42);
    const shapes = MOODS.map((m) => JSON.stringify(ds.map((d) => place(d, m))));
    expect(new Set(shapes).size).toBe(MOODS.length);
    const lift = (m: (typeof MOODS)[number]) => ds.reduce((s, d) => s + place(d, m).y, 0) / ds.length;
    expect(lift('love')).toBeLessThan(lift('neutral')); // love lifts
    expect(ds.reduce((s, d) => s + place(d, 'skip').x, 0)).toBeGreaterThan(ds.reduce((s, d) => s + d.x, 0)); // skip drifts
  });
});
