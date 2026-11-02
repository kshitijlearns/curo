import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

// v2.3: purple and white only. Every colour in the web app must be a purple or a white, so an
// old blue, pink or grey can't creep back in.
function files(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    if (statSync(p).isDirectory()) return f === 'api' ? [] : files(p);
    return /\.(css|tsx?|svg)$/.test(f) && !/\.test\./.test(f) ? [p] : [];
  });
}

/** Purple: blue well above green, red above green. White and near-white purples pass. */
function isPurple(hex: string) {
  const h = hex.length === 4 ? hex.slice(1).replace(/./g, (c) => c + c) : hex.slice(1);
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  if (r === 255 && g === 255 && b === 255) return true;
  return b > g && r > g && b >= r;
}

describe('the palette', () => {
  it('has no colour outside purple and white', () => {
    const bad: string[] = [];
    for (const f of files(join(process.cwd(), 'src'))) {
      for (const m of readFileSync(f, 'utf8').matchAll(/#[0-9a-fA-F]{6}\b|(?<![\w&])#[0-9a-fA-F]{3}\b(?!-)/g)) {
        if (!isPurple(m[0])) bad.push(`${f}: ${m[0]}`);
      }
    }
    expect(bad).toEqual([]);
  });
});
