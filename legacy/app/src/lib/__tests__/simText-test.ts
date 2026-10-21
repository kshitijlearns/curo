import type { Simulation } from '@/api/simulator';

import { formatRate, reportRow, scoreDelta } from '../simText';

const audience = (score: number, summary: string) => ({
  score,
  label: 'Around your baseline',
  summary,
  working: [],
  holding: [
    {
      key: 'cta_type:comment_prompt',
      feature: 'cta_type',
      value: 'comment_prompt',
      metric: 'share_rate',
      text: 'It has a comment prompt. Your reels with a send-to-a-friend prompt got 1.43× your usual shares per view (10 reels).',
      evidence: [],
    },
  ],
  edit_ids: [],
});

const sim = {
  id: 's2',
  status: 'done',
  audience: 'both',
  scores: { followers: 67, new: 71, both: 67 },
  created_at: '2027-08-23T04:30:00Z',
  result: {
    method: 't9-v0',
    video: { duration_s: 32 },
    caption: '',
    linked: false,
    audiences: {
      followers: audience(67, 'Strongest on shares.'),
      new: audience(71, 'Strongest on shares and views.'),
      both: audience(67, 'Strongest on shares and comments.'),
    },
    report: [
      {
        metric: 'views',
        label: 'views',
        known: true,
        baseline: 62150,
        low: 52579,
        mid: 67619,
        high: 92417,
        change_pct: 9,
      },
      { metric: 'like_rate', label: 'likes', known: false },
      {
        metric: 'comment_rate',
        label: 'comments',
        known: true,
        baseline: 0.003,
        low: 0.001,
        mid: 0.0034,
        high: 0.0067,
        change_pct: 12,
      },
      {
        metric: 'share_rate',
        label: 'shares',
        known: true,
        baseline: 0.0073,
        low: 0.0079,
        mid: 0.0112,
        high: 0.0188,
        change_pct: 53,
      },
    ],
    best_time: null,
    accuracy: 'No record yet.',
    dna: { content: [], production: [], trend: [] },
    compare: [],
    notes: [],
    basis: { neighbours: 15, own_neighbours: 1, own_reels: 33, history: 48, peer_accounts: 10 },
    previous: { simulation_id: 's1', scores: { followers: 42, new: 50, both: 48 } },
  },
} as unknown as Simulation;

describe('the report', () => {
  it('shows rates as percentages and views as a range', () => {
    expect(formatRate(0.0444)).toBe('4.4%');
    expect(formatRate(0.00317)).toBe('0.32%');
    expect(formatRate(0.05)).toBe('5%');
    expect(formatRate(null)).toBe('—');
    const views = reportRow(sim.result!.report[0])!;
    expect(views.value).toBe('53K – 92K');
    expect(views.base).toBe('62K median');
    expect(views.change).toBe('+9%');
    const shares = reportRow(sim.result!.report[3])!;
    expect([shares.value, shares.base, shares.change]).toEqual(['1.1%', '0.73%', '+53%']);
  });

  it('leaves an unknown count unknown, never zero', () => {
    expect(reportRow(sim.result!.report[1])).toBeNull();
  });

  it('shows the change since the run before for the audience on screen', () => {
    expect(scoreDelta(sim, 'both')).toBe(19);
    expect(scoreDelta(sim, 'new')).toBe(21);
    expect(scoreDelta({ ...sim, result: { ...sim.result!, previous: null } }, 'both')).toBeNull();
  });
});
