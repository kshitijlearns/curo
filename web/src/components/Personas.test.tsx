import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { useEffect } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AppProvider, useApp } from '@/state/app';

const personas = [
  { id: 'p1', slot: 1, name: 'The Festive Planner', short_name: 'Festive Planner', share: 0.31, color: 'blue', avatar_seed: 11, is_starter: false },
  { id: 'p2', slot: 2, name: 'The Budget Stylist', short_name: 'Budget Stylist', share: 0.27, color: 'lavender', avatar_seed: 22, is_starter: false },
  { id: 'p3', slot: 3, name: 'The Loyal Fan', short_name: 'Loyal Fan', share: 0.23, color: 'pink', avatar_seed: 33, is_starter: false },
  { id: 'p4', slot: 4, name: 'The Friend Tagger', short_name: 'Friend Tagger', share: 0.19, color: 'ink', avatar_seed: 44, is_starter: false },
];
const reactions = {
  status: 'ready',
  summary: '3 of 4 follower groups are in. The Budget Stylist isn’t sure.',
  label: 'x',
  reactions: personas.map((p, i) => ({
    persona_id: p.id,
    name: p.name,
    short_name: p.short_name,
    color: p.color,
    avatar_seed: p.avatar_seed,
    share: p.share,
    is_starter: false,
    reaction: ['watch_all', 'scroll_past', 'watch', 'watch'][i],
    reaction_label: ['Would watch it all', 'Might scroll past', 'Would watch', 'Would watch'][i],
    mood: ['love', 'unsure', 'like', 'like'][i],
    badge: ['Love', 'Unsure', 'Like', 'Like'][i],
    score: [82, 48, 70, 61][i],
    score_model: 80,
    score_code: 60,
    would: { like: true, comment: i === 0, share: false, save: true },
    opinion: `Opinion ${i}`,
    win_them_over: `Change ${i}`,
    evidence: [`Evidence ${i}`],
  })),
};

let fetching = false;
vi.mock('@/lib/hooks', () => ({
  usePersonas: () => ({ data: { status: 'ready', personas, label: 'x' } }),
  usePersonaReactions: () => ({ data: fetching ? undefined : reactions, isFetching: fetching }),
  usePersona: () => ({ data: undefined }),
  usePersonaChatHistory: () => ({ data: [] }),
}));

import { PersonaRow } from './Personas';

function Harness({ typing = false, busy = false, onSend = () => {} }: { typing?: boolean; busy?: boolean; onSend?: (t: string) => void }) {
  const s = useApp();
  useEffect(() => {
    s.setPersonaTarget({ projectId: 'proj', key: 'script:1', target: { target_type: 'script' } });
    s.setComposer({ placeholder: 'x', busy, onSend });
    s.setTyping(typing);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [typing, busy]);
  return <PersonaRow />;
}

function mount(props: Parameters<typeof Harness>[0] = {}) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <AppProvider>
        <Harness {...props} />
      </AppProvider>
    </QueryClientProvider>,
  );
}

const moods = (el: HTMLElement) => Array.from(el.querySelectorAll('svg.pa')).map((s) => s.getAttribute('data-mood'));

beforeEach(() => {
  fetching = false;
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} }));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('the Studio persona row', () => {
  it('shows each persona’s own mood and badge after a score', () => {
    const { container } = mount();
    expect(moods(container)).toEqual(['love', 'unsure', 'like', 'like']);
    expect(screen.getByText('3 of 4 follower groups are in. The Budget Stylist isn’t sure.')).toBeTruthy();
    expect(screen.getAllByText(/^(Love|Like|Unsure|Skip)$/)).toHaveLength(4);
    expect(screen.getByText('Festive Planner')).toBeTruthy();
  });

  it('listens while the creator types and thinks while scoring', () => {
    const typing = mount({ typing: true });
    expect(moods(typing.container)).toEqual(['listening', 'listening', 'listening', 'listening']);
    cleanup();
    const busy = mount({ busy: true });
    expect(moods(busy.container)).toEqual(['thinking', 'thinking', 'thinking', 'thinking']);
    cleanup();
    fetching = true;
    const loading = mount();
    expect(moods(loading.container)).toEqual(['thinking', 'thinking', 'thinking', 'thinking']);
  });

  it('opens a keyboard-accessible popover with that persona’s take, closes on Esc', () => {
    const sent: string[] = [];
    mount({ onSend: (t) => sent.push(t) });
    const avatar = screen.getByRole('button', { name: /The Budget Stylist: Might scroll past/ });
    avatar.focus();
    fireEvent.click(avatar);
    const dialog = screen.getByRole('dialog', { name: 'The Budget Stylist' });
    expect(within(dialog).getByText('Might scroll past')).toBeTruthy();
    expect(within(dialog).getByText('“Opinion 1”')).toBeTruthy();
    expect(within(dialog).getByText(/\(simulated\)/)).toBeTruthy();
    expect(dialog.contains(document.activeElement)).toBe(true); // focus moved in
    act(() => {
      fireEvent.keyDown(window, { key: 'Escape' });
    });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(avatar); // focus returned

    fireEvent.click(avatar);
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Apply' }));
    expect(sent).toEqual(['Change 1']); // sent to the Studio chat as a revision
  });
});
