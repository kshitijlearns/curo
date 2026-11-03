import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { PALETTE } from '@/lib/palette';

// v3 (D245): colour blocks. Every hex colour in the web app must come from lib/palette.ts, so an
// off-palette colour can't creep in. (rgba() tints of these are fine and aren't checked.)
function files(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    if (statSync(p).isDirectory()) return f === 'api' ? [] : files(p);
    return /\.(css|tsx?|svg)$/.test(f) && !/\.test\./.test(f) && f !== 'palette.ts' ? [p] : [];
  });
}

const allowed = new Set(Object.values(PALETTE).map((h) => h.toLowerCase()));
const expand = (hex: string) => (hex.length === 4 ? `#${hex.slice(1).replace(/./g, (c) => c + c)}` : hex).toLowerCase();

describe('the palette', () => {
  it('has no colour outside lib/palette.ts', () => {
    const bad: string[] = [];
    for (const f of files(join(process.cwd(), 'src'))) {
      for (const m of readFileSync(f, 'utf8').matchAll(/#[0-9a-fA-F]{6}\b|(?<![\w&])#[0-9a-fA-F]{3}\b(?!-)/g)) {
        if (!allowed.has(expand(m[0]))) bad.push(`${f}: ${m[0]}`);
      }
    }
    expect(bad).toEqual([]);
  });

  it('defines every palette colour as a CSS token', () => {
    const css = readFileSync(join(process.cwd(), 'src/app/globals.css'), 'utf8').toLowerCase();
    for (const hex of allowed) expect(css).toContain(hex);
  });
});
