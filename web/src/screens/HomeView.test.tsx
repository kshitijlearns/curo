import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AppProvider } from '@/state/app';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push() {}, replace() {} }) }));
vi.mock('next/link', () => ({ default: ({ href, children, ...rest }: any) => <a href={href} {...rest}>{children}</a> }));

const card = {
  id: 'p1',
  slot: 1,
  name: 'The Festive Planner',
  short_name: 'Festive Planner',
  tagline: 'Plans every festival look weeks ahead.',
  share: 0.31,
  share_pct: 31,
  color: 'blue',
  avatar_seed: 11,
  confidence: 'high',
  is_starter: false,
  mood: 'love',
  meter: 5,
  meter_word: 'Big fan',
  thought: { thought: 'Your festive looks are my go-to.', mood: 'love', loves: ['festive looks', 'quick reveals'], wants_more: ['budget versions'] },
  n_comments: 214,
  n_reels: 18,
  evidence_line: 'From 214 comments across 18 reels · updated 3 Oct.',
  updated_at: '2027-10-03T00:00:00Z',
};
let personasStatus: 'ready' | 'building' = 'ready';
vi.mock('@/lib/hooks', () => ({
  useMe: () => ({ data: { account: { username: 'curo.demo' }, is_anonymous: false } }),
  usePersonas: () => ({
    isLoading: false,
    data:
      personasStatus === 'ready'
        ? { status: 'ready', summary: '3 of 4 of your follower groups are loving your recent reels.', early_guess: false, label: 'x', personas: [card, { ...card, id: 'p2', slot: 2 }, { ...card, id: 'p3', slot: 3 }, { ...card, id: 'p4', slot: 4 }] }
        : { status: 'building', label: 'x', personas: [] },
  }),
  usePersona: () => ({ data: undefined }),
  usePersonaChatHistory: () => ({ data: [] }),
  useLatestRecap: () => ({ isLoading: false, isSuccess: true, data: null }),
  useOnboardingStatus: () => ({ data: undefined }),
  useOpportunities: () => ({ isLoading: false, data: [] }),
  useTrends: () => ({ isLoading: false, data: [] }),
}));

import { HomeView } from './HomeView';

function mount() {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} }));
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <AppProvider>
        <HomeView />
      </AppProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('Home', () => {
  it('shows the v3 sections in order, followers first', () => {
    mount();
    const titles = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(titles).toEqual(['Your followers', 'They want more of', 'Your Creator Recap', 'Opportunity areas', 'Trending for you']);
    expect(screen.queryByText('What your followers will love')).toBeNull();
  });

  it('puts the personas on a podium and ranks them, with how each one feels in words and the label', () => {
    mount();
    expect(screen.getByText('3 of 4 of your follower groups are loving your recent reels.')).toBeTruthy();
    // On the podium, each orb is labelled with the persona's name, share and mood.
    expect(screen.getAllByRole('img', { name: 'The Festive Planner, 31% of your comments, mood: love' })).toHaveLength(4);
    expect(screen.getAllByText('31%')).toHaveLength(4);
    // The ranking: one row each, its mood meter in words.
    expect(screen.getAllByRole('button', { name: 'The Festive Planner, Big fan: open details' })).toHaveLength(4);
    expect(screen.getAllByRole('meter')[0].getAttribute('aria-valuetext')).toBe('Big fan');
    expect(screen.getByText('Built from your public comments. Personas are summaries, not real people.')).toBeTruthy();
  });

  it('turns what each persona wants more of into a one-tap Studio start', () => {
    mount();
    expect(screen.getAllByRole('button', { name: 'Make this: budget versions' })).toHaveLength(4);
  });

  it('shows breathing skeletons while the personas are being built', () => {
    personasStatus = 'building';
    mount();
    expect(screen.getAllByRole('img', { name: 'Building your follower personas' }).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Meeting your followers…').length).toBeGreaterThan(0);
    expect(screen.queryByRole('heading', { name: 'They want more of' })).toBeNull();
    personasStatus = 'ready';
  });
});
