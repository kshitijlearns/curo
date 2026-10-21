/** Studio wording and colours from the prototype; the numbers behind them come from the API. */
import { colors } from '@/theme';

export type PartKey = 'H' | 'A' | 'P' | 'T' | 'N';
export type Slot = 'proven' | 'adapted' | 'explore';
export type Verdict = 'Strong' | 'Worth trying' | 'Risky';
export type NoteType = 'hook' | 'comments' | 'likes' | 'shares';

export const PART_LABELS: Record<PartKey, string> = {
  H: 'Your history',
  A: 'Audience',
  P: 'Peers',
  T: 'Trend',
  N: 'Novelty',
};
export const PART_ORDER: PartKey[] = ['H', 'A', 'P', 'T', 'N'];

export const SLOT_LABELS: Record<Slot, string> = {
  proven: 'Proven',
  adapted: 'Adapted',
  explore: 'Explore',
};

/** A note's highlight on its script line (never "saves": they aren't public). */
export const NOTE_BG: Record<NoteType, string> = {
  hook: colors.pink,
  comments: colors.lavender,
  likes: colors.gray,
  shares: colors.lavender,
};

export const MAX_HASHTAGS = 5;
