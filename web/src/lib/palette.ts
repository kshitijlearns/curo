/**
 * CURO's colours (v3, "colour blocks"). Every colour in the web app comes from this list: the
 * CSS tokens in globals.css, the persona orbs, the recap and the charts. palette.test.ts fails
 * on any hex code outside it, so a stray colour can't creep in.
 *
 * Cream paper, near-black ink, and seven saturated blocks. Ink text sits on every block except
 * violet and ink, which carry white.
 */
export const PALETTE = {
  ink: '#141414',
  ink2: '#262626',
  cream: '#F2EEE5',
  paper: '#FBF8F2',
  sand: '#E4DED1',
  white: '#FFFFFF',
  violet: '#7B5CFA',
  violetDeep: '#4B2FD1',
  lilac: '#CFC2FF',
  lemon: '#FFD449',
  coral: '#FF6A55',
  lime: '#CDEA6A',
  pink: '#FFB5E3',
  sky: '#A6D5FF',
  teal: '#0E8F6E',
} as const;

export type Block = 'violet' | 'lemon' | 'coral' | 'lime' | 'pink' | 'sky' | 'ink' | 'lilac' | 'paper';

/** A rotating set of blocks for lists of cards (stacked decks, ideas, trends). */
export const BLOCKS: Block[] = ['violet', 'lemon', 'coral', 'lime', 'sky', 'pink'];

export const blockAt = (i: number): Block => BLOCKS[((i % BLOCKS.length) + BLOCKS.length) % BLOCKS.length];

/** A persona's stored colour name → its block (D242's names are kept so identities stay). */
export const PERSONA_BLOCK: Record<string, Block> = {
  blue: 'sky',
  lavender: 'violet',
  pink: 'pink',
  ink: 'ink',
  gray: 'paper',
};

/** A score (0–1) → the block that reads it: lime is strong, lemon fair, coral weak. */
export const scoreBlock = (share: number | null | undefined): Block =>
  share === null || share === undefined ? 'paper' : share >= 0.6 ? 'lime' : share >= 0.4 ? 'lemon' : 'coral';
