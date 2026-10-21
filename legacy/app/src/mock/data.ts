/**
 * Shared wording ported from the prototype's <script> (reference/prototype/pages/main-screen/
 * logic.js): the phase names and the opportunity tag colours. Every screen reads its data from
 * the API; nothing here is data any more.
 *
 * Changes from the prototype (see docs/DECISIONS.md): phases use the logic doc's five-phase
 * model (D11).
 */
import { colors } from '@/theme';

/* ------------------------------------------------------------------ reel phases */

export type PhaseId = 'testing' | 'growing' | 'peak' | 'slowing' | 'longtail';

export const PHASES: { id: PhaseId; label: string }[] = [
  { id: 'testing', label: 'Testing' },
  { id: 'growing', label: 'Growing' },
  { id: 'peak', label: 'Peak' },
  { id: 'slowing', label: 'Slowing' },
  { id: 'longtail', label: 'Long tail' },
];

export type MetricValue = { value: string | null; change: number | null };

/* ------------------------------------------------------------------ opportunity tags */

export type OppTag = 'Competitor' | 'Trend' | 'Your content' | 'Audience';

export const TAG_STYLE: Record<OppTag, { bg: string; fg: string }> = {
  Competitor: { bg: colors.pink, fg: colors.ink },
  Trend: { bg: colors.ink, fg: colors.white },
  'Your content': { bg: colors.lavender, fg: colors.ink },
  Audience: { bg: colors.gray, fg: colors.ink },
};
