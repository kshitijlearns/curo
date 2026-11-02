import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { MOODS } from '@/lib/avatar';

import { PersonaAvatar } from './PersonaAvatar';

function motion(reduce: boolean) {
  vi.stubGlobal('matchMedia', (q: string) => ({
    matches: reduce && q.includes('reduce'),
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('PersonaAvatar', () => {
  it('renders every mood with an accessible label', () => {
    motion(false);
    for (const mood of MOODS) {
      render(<PersonaAvatar seed={42} color="blue" mood={mood} name="The Festive Planner" share={0.31} />);
      const img = screen.getByRole('img', { name: `The Festive Planner, 31% of your comments, mood: ${mood}` });
      expect(img.getAttribute('data-mood')).toBe(mood);
      expect(img.querySelectorAll('circle.pa-dot').length).toBeGreaterThanOrEqual(18);
      cleanup();
    }
  });

  it('moves with motion on, and is static with reduced motion', () => {
    motion(false);
    const { container, unmount } = render(<PersonaAvatar seed={7} color="lavender" mood="thinking" />);
    expect(container.querySelector('.pa-anim.pa-thinking')).not.toBeNull();
    expect(container.querySelector('svg')?.getAttribute('data-static')).toBeNull();
    unmount();
    motion(true);
    const reduced = render(<PersonaAvatar seed={7} color="lavender" mood="thinking" />);
    expect(reduced.container.querySelector('.pa-anim')).toBeNull();
    expect(reduced.container.querySelector('svg')?.getAttribute('data-static')).toBe('true');
  });

  it('is static when animated is off, and shows the Studio states over the mood', () => {
    motion(false);
    const { container, rerender } = render(<PersonaAvatar seed={7} color="pink" mood="love" animated={false} />);
    expect(container.querySelector('.pa-anim')).toBeNull();
    rerender(<PersonaAvatar seed={7} color="pink" mood="love" state="listening" />);
    expect(container.querySelector('svg')?.getAttribute('data-mood')).toBe('listening');
    rerender(<PersonaAvatar seed={7} color="pink" mood="love" state="thinking" />);
    expect(container.querySelector('svg')?.getAttribute('data-mood')).toBe('thinking');
  });

  it('is a gradient orb with its dots inside, and the same seed gives the same dots', () => {
    motion(false);
    const dotsOf = (c: HTMLElement) => Array.from(c.querySelectorAll('circle.pa-dot')).map((d) => `${d.getAttribute('cx')},${d.getAttribute('cy')}`);
    const a = render(<PersonaAvatar seed={99} color="pink" />);
    expect(a.container.querySelector('radialGradient')).not.toBeNull();
    const orb = a.container.querySelector('circle.pa-orb');
    expect(orb?.getAttribute('fill')).toContain(a.container.querySelector('radialGradient')?.id);
    const first = dotsOf(a.container);
    cleanup();
    const b = render(<PersonaAvatar seed={99} color="blue" />);
    expect(dotsOf(b.container)).toEqual(first);
  });
});
