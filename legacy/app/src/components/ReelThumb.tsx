import { StyleSheet, View } from 'react-native';
import Svg, { G, Path, Polygon, Rect } from 'react-native-svg';

import { Icon } from './Icon';
import { Txt } from './Txt';
import { colors } from '@/theme';

/** The four thumbnail tones from the prototype (six-colour palette only). */
const TONES = [
  {
    bg: colors.blue,
    fg: colors.white,
    beam: colors.lavender,
    leaf: colors.ink,
    floor: colors.lavender,
    pot: colors.pink,
  },
  {
    bg: colors.pink,
    fg: colors.ink,
    beam: colors.white,
    leaf: colors.ink,
    floor: colors.white,
    pot: colors.blue,
  },
  {
    bg: colors.lavender,
    fg: colors.ink,
    beam: colors.white,
    leaf: colors.blue,
    floor: colors.gray,
    pot: colors.ink,
  },
  {
    bg: colors.ink,
    fg: colors.white,
    beam: colors.blue,
    leaf: colors.lavender,
    floor: colors.blue,
    pot: colors.pink,
  },
];

type Props = {
  title?: string;
  duration?: string;
  tone?: number;
  titleSize?: number;
  /** Illustration only: no title, no duration pill. */
  compact?: boolean;
  height?: number;
};

/** Reel thumbnail placeholder: stylised studio light and plant, title and duration. */
export function ReelThumb({
  title = '',
  duration = '',
  tone = 0,
  titleSize = 18,
  compact = false,
  height,
}: Props) {
  const n = TONES.length;
  const t = TONES[((tone % n) + n) % n];
  return (
    <View style={[styles.root, { backgroundColor: t.bg }, height ? { height } : { flex: 1 }]}>
      <Svg
        viewBox="0 0 180 280"
        preserveAspectRatio="xMidYMid slice"
        style={StyleSheet.absoluteFill}
      >
        <Polygon points="70,0 112,0 40,280 -2,280" fill={t.beam} opacity={0.5} />
        <Polygon points="132,0 152,0 96,280 76,280" fill={t.beam} opacity={0.35} />
        <Rect x={0} y={214} width={180} height={66} fill={t.floor} />
        <G transform="translate(96 96)">
          <Path
            d="M50 120 C 48 90, 44 64, 36 40"
            stroke={t.leaf}
            strokeWidth={2.5}
            fill="none"
            strokeLinecap="round"
          />
          <Path d="M36 40 C 22 30, 12 34, 8 46 C 20 50, 30 48, 36 40 Z" fill={t.leaf} />
          <Path d="M40 56 C 54 42, 66 46, 72 54 C 60 64, 50 64, 40 56 Z" fill={t.leaf} />
          <Path d="M44 76 C 28 66, 16 72, 12 84 C 26 88, 38 86, 44 76 Z" fill={t.leaf} />
          <Path d="M36 40 C 38 24, 46 14, 58 12 C 56 26, 48 36, 36 40 Z" fill={t.leaf} />
          <Rect x={36} y={108} width={28} height={24} rx={4} fill={t.pot} />
        </G>
      </Svg>
      {compact ? null : (
        <>
          <Txt
            size={titleSize}
            weight={600}
            lh={1.18}
            ls={-0.005}
            color={t.fg}
            style={styles.title}
          >
            {title}
          </Txt>
          <View style={styles.duration}>
            <Icon name="play" size={13} color={colors.blue} />
            <Txt size={13} weight={600}>
              {duration}
            </Txt>
          </View>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { position: 'relative', width: '100%', minHeight: 40, overflow: 'hidden' },
  title: { position: 'absolute', top: 16, left: 14, right: 14 },
  duration: {
    position: 'absolute',
    left: 12,
    bottom: 12,
    height: 34,
    paddingLeft: 10,
    paddingRight: 13,
    borderRadius: 17,
    backgroundColor: colors.white,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
  },
});
