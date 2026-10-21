import type { Schemas } from './client';
import { formatCount, formatDuration } from '@/lib/format';
import type { MetricValue } from '@/mock/data';

export type ReelVM = {
  id: string;
  title: string;
  tone: number;
  duration: string;
  permalink: string;
  metrics: { views: MetricValue; likes: MetricValue; shares: MetricValue; comments: MetricValue };
  comparedWith: 'simulation' | 'usual' | null;
  snapshots: number;
  lastSnapshotAt: string | null;
  seenLate: boolean;
};

const metric = (
  value: number | null | undefined,
  change: number | null | undefined,
): MetricValue => ({
  value: formatCount(value ?? null),
  change: change ?? null,
});

/** API reel card → what the carousel shows. Unknown counts stay null (shown as "–"). */
export function toReelVM(card: Schemas['ReelCard']): ReelVM {
  const m = card.metrics;
  const c = card.changes ?? {};
  return {
    id: card.id,
    title: card.title,
    tone: card.tone,
    duration: formatDuration(card.duration_s),
    permalink: card.permalink,
    metrics: {
      views: metric(m.views, c.views),
      likes: metric(m.likes, c.likes),
      shares: metric(m.shares, c.shares),
      comments: metric(m.comments, c.comments),
    },
    comparedWith: card.compared_with ?? null,
    snapshots: card.snapshots ?? 0,
    lastSnapshotAt: card.last_snapshot_at ?? null,
    seenLate: card.seen_late ?? false,
  };
}

export const COMPARISON_NOTES = {
  simulation:
    'Arrows compare actual results with Curo’s pre-publish simulation. Public counts only.',
  usual:
    'Arrows compare actual results with your usual results at this age (no simulation was run). Public counts only.',
  none: 'Public counts only.',
} as const;
