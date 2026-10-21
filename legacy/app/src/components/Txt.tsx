import { Text, type TextProps } from 'react-native';

import { colors, font, type Weight } from '@/theme';

type Props = TextProps & {
  size?: number;
  weight?: Weight;
  color?: string;
  /** Line height as a multiple of the font size, like CSS `line-height: 1.5`. */
  lh?: number;
  /** Letter spacing in em, like CSS `letter-spacing: .1em`. */
  ls?: number;
  align?: 'left' | 'center' | 'right';
  upper?: boolean;
  italic?: boolean;
  tabular?: boolean;
};

/** Text in CURO's font. Sizes and spacing use the prototype's CSS units. */
export function Txt({
  size = 14,
  weight = 400,
  color = colors.ink,
  lh,
  ls,
  align,
  upper,
  italic,
  tabular,
  style,
  ...rest
}: Props) {
  return (
    <Text
      maxFontSizeMultiplier={1.25}
      {...rest}
      style={[
        font(weight, italic),
        {
          fontSize: size,
          color,
          lineHeight: lh ? Math.round(size * lh) : undefined,
          letterSpacing: ls ? ls * size : undefined,
          textAlign: align,
          textTransform: upper ? 'uppercase' : undefined,
          fontVariant: tabular ? ['tabular-nums'] : undefined,
        },
        style,
      ]}
    />
  );
}

/** Small uppercase label, e.g. "OPPORTUNITY AREA". */
export function Eyebrow({
  children,
  color,
  ls = 0.1,
}: {
  children: React.ReactNode;
  color?: string;
  ls?: number;
}) {
  return (
    <Txt size={11.5} weight={600} ls={ls} upper color={color}>
      {children}
    </Txt>
  );
}
