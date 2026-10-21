/**
 * CURO's palette: exactly six colours, no gradients anywhere.
 * `muted` is ink at 72% opacity (secondary text), as in the prototype.
 */
export const colors = {
  blue: '#5B73F2',
  lavender: '#C3BFF2',
  pink: '#F2D4E2',
  white: '#FFFFFF',
  gray: '#E4E4EC',
  ink: '#242424',
  muted: 'rgba(36,36,36,0.72)',
} as const;

export type ColorName = keyof typeof colors;

/** The six brand colours (everything except derived opacities). */
export const PALETTE = [
  colors.blue,
  colors.lavender,
  colors.pink,
  colors.white,
  colors.gray,
  colors.ink,
] as const;
