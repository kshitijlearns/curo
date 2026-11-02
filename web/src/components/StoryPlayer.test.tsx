import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { S } from '@/lib/api';

import { StoryPlayer } from './StoryPlayer';

const crew = ['Friend Tagger', 'Budget Stylist', 'Loyal Fan', 'Festive Planner'].map((short, i) => ({
  id: `p${i}`,
  name: `The ${short}`,
  short_name: short,
  share_pct: [34, 29, 22, 15][i],
  color: ['blue', 'lavender', 'pink', 'ink'][i],
  avatar_seed: 100 + i,
}));
const visual = { bg: 'lavender', fg: 'ink', accent: 'blue', milestone: false, seconds: 6 };
const slide = (slide_id: string, facts: Record<string, unknown> = {}, bg = 'lavender') => ({
  slide_id,
  facts: { display: ['x'], how: 'x', ...facts },
  copy: { headline: `Headline ${slide_id}`, subline: 'Sub' },
  visual: { ...visual, bg },
});
const recap = {
  id: 'r1',
  period_label: 'Your story so far',
  period_start: '2027-05-01',
  slides: [
    slide('intro'),
    slide('views_total', { views: 1200 }, 'ink'),
    slide('followers_intro', { personas: crew }),
    slide('persona_1', { ...crew[0], tagline: 'Sends your reels to the group chat.', comes_for: ['your looks'], thought: 'I come for relatable moments.' }),
    slide('followers_summary', { personas: crew }),
  ],
} as unknown as S['Recap'];

const next = () => fireEvent.keyDown(window, { key: 'ArrowRight' });

beforeEach(() => {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('reduce'), media: q, addEventListener() {}, removeEventListener() {} }));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('the Creator Recap', () => {
  it('opens with the four persona orbs, and one peeks in on the slides after', () => {
    render(<StoryPlayer recap={recap} onClose={() => {}} />);
    expect(document.querySelectorAll('.story-body svg.pa')).toHaveLength(4);
    expect(document.querySelector('.cameo')?.textContent).toContain('Psst');
    next();
    expect(document.querySelector('.cameo svg.pa')).not.toBeNull();
    expect(document.querySelector('.story-col')?.getAttribute('data-scene')).toBe('deep');
    expect(screen.getByText('Built from your public comments. Personas are summaries, not real people.')).toBeTruthy();
  });

  it('gives a persona its own big orb, share sticker and words', () => {
    render(<StoryPlayer recap={recap} start={3} onClose={() => {}} />);
    expect(screen.getByRole('img', { name: 'The Friend Tagger, 34% of your comments, mood: love' })).toBeTruthy();
    expect(screen.getByText('34%')).toBeTruthy();
    expect(screen.getByText('“I come for relatable moments.”')).toBeTruthy();
    expect(document.querySelector('.cameo')).toBeNull(); // the persona has the slide to itself
    expect(document.querySelector('.story-col')?.getAttribute('data-scene')).toBe('violet');
  });

  it('shows all four in the summary, and a tap opens that persona after the recap', () => {
    const onClose = vi.fn();
    render(<StoryPlayer recap={recap} start={4} onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: /The Loyal Fan, 22% of your comments/ }));
    expect(onClose).toHaveBeenCalled();
    expect(sessionStorage.getItem('curo.openPersona')).toBe('p2');
  });
});
