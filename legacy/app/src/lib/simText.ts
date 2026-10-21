/**
 * Simulator wording from the prototype, and the result's numbers as text. Every number shown
 * comes from the API's result; nothing here estimates anything. (Questions about a result go
 * to Ask Curo: api/chat.ts.)
 */
import { formatCount } from './format';
import type { SimAudienceId, SimReportRow, Simulation } from '@/api/simulator';

export type DnaTab = 'content' | 'production' | 'trend';
export type Audience = SimAudienceId;

export const AUDIENCES: { id: Audience; label: string }[] = [
  { id: 'followers', label: 'Followers' },
  { id: 'new', label: 'New audiences' },
  { id: 'both', label: 'Both' },
];

/** The loading screen's steps, one per step of the job (api/simulator.ts SIM_STEP_KEYS). */
export const SIM_STEPS = [
  'Reading Content DNA',
  'Reading Production DNA',
  'Checking Trend DNA',
  'Comparing with your past reels',
  'Estimating audience response',
];

export const METRIC_NAMES: Record<SimReportRow['metric'], string> = {
  views: 'Views',
  like_rate: 'Like rate',
  comment_rate: 'Comment rate',
  share_rate: 'Share rate',
};

/** A rate per view as a percentage: 0.0444 → "4.4%", 0.00317 → "0.32%". */
export function formatRate(x: number | null | undefined): string {
  if (x == null) return '—';
  const pct = x * 100;
  const digits = pct >= 1 ? 1 : 2;
  return `${pct.toFixed(digits).replace(/\.?0+$/, '')}%`;
}

/** One report row as the prototype shows it: the estimate, and the change against the usual. */
export function reportRow(row: SimReportRow): {
  name: string;
  value: string;
  base: string;
  above: boolean;
  change: string;
  pred: number;
  baseline: number;
  max: number;
} | null {
  if (!row.known || row.mid == null || row.baseline == null) return null;
  const views = row.metric === 'views';
  const fmt = (x: number | null | undefined) =>
    views ? (formatCount(Math.round(x ?? 0)) ?? '—') : formatRate(x);
  const pct = row.change_pct ?? 0;
  return {
    name: METRIC_NAMES[row.metric],
    value: views ? `${fmt(row.low)} – ${fmt(row.high)}` : fmt(row.mid),
    base: views ? `${fmt(row.baseline)} median` : fmt(row.baseline),
    above: pct >= 0,
    change: `${pct >= 0 ? '+' : ''}${pct}%`,
    pred: row.mid,
    baseline: row.baseline,
    max: Math.max(row.mid, row.baseline) * 1.5,
  };
}

/** "+19 since last run" against the run before (a re-run), for the audience on screen. */
export function scoreDelta(sim: Simulation, audience: Audience): number | null {
  const prev = sim.result?.previous?.scores?.[audience];
  const now = sim.scores?.[audience];
  return prev == null || now == null ? null : now - prev;
}
