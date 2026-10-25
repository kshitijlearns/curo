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

  it('gives light colours a hairline ring and the same seed the same dots', () => {
    motion(false);
    const a = render(<PersonaAvatar seed={99} color="pink" />);
    expect(a.container.querySelector('circle[stroke="#E4E4EC"]')).not.toBeNull();
    const first = a.container.innerHTML;
    cleanup();
    const b = render(<PersonaAvatar seed={99} color="pink" />);
    expect(b.container.innerHTML).toBe(first);
    cleanup();
    const blue = render(<PersonaAvatar seed={99} color="blue" />);
    expect(blue.container.querySelector('circle[stroke="#E4E4EC"]')).toBeNull();
  });
});
