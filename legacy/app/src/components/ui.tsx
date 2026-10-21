/** Small building blocks shared by every screen, matching the prototype's styles. */
import { Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import Animated from 'react-native-reanimated';

import { Icon, type IconName } from './Icon';
import { Press } from './motion';
import { Txt } from './Txt';
import { colors, springOn } from '@/theme';

/* ------------------------------------------------------------------ buttons */

type PrimaryProps = {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  /** Fades the button without disabling presses (prototype `opacity` binding). */
  dim?: boolean;
  height?: number;
  fontSize?: number;
  icon?: IconName;
  style?: StyleProp<ViewStyle>;
};

/** Blue pill with the label on the left and a white circle + arrow on the right. */
export function PrimaryButton({
  label,
  onPress,
  disabled,
  dim,
  height = 56,
  fontSize = 17,
  icon = 'arrowRight',
  style,
}: PrimaryProps) {
  const circle = height - 12;
  return (
    <Press
      onPress={onPress}
      disabled={disabled}
      accessibilityLabel={label}
      style={[
        styles.primary,
        { height, borderRadius: height / 2, paddingLeft: 24, opacity: dim || disabled ? 0.45 : 1 },
        style,
      ]}
    >
      <Txt size={fontSize} weight={600} color={colors.white} style={{ flex: 1 }} numberOfLines={1}>
        {label}
      </Txt>
      <View
        style={[styles.primaryCircle, { width: circle, height: circle, borderRadius: circle / 2 }]}
      >
        <Icon name={icon} size={height >= 58 ? 20 : 18} color={colors.blue} strokeWidth={2} />
      </View>
    </Press>
  );
}

/** Blue pill with a centred label and an optional leading icon (Generate Script, Save draft). */
export function CenterButton({
  label,
  onPress,
  disabled,
  dim,
  height = 56,
  fontSize = 17,
  icon,
  color = colors.blue,
  style,
}: PrimaryProps & { color?: string }) {
  return (
    <Press
      onPress={onPress}
      disabled={disabled}
      accessibilityLabel={label}
      style={[
        styles.center,
        {
          height,
          borderRadius: height / 2,
          backgroundColor: color,
          opacity: dim || disabled ? 0.45 : 1,
        },
        style,
      ]}
    >
      {icon ? (
        <Icon
          name={icon}
          size={icon === 'sparkle' ? 16 : 18}
          color={colors.white}
          strokeWidth={2}
        />
      ) : null}
      <Txt size={fontSize} weight={600} color={colors.white}>
        {label}
      </Txt>
    </Press>
  );
}

/** Ink pill with a white arrow circle ("Explore more"). */
export function DarkButton({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Press onPress={onPress} accessibilityLabel={label} style={styles.dark}>
      <Txt size={14.5} weight={600} color={colors.white}>
        {label}
      </Txt>
      <View style={styles.darkCircle}>
        <Icon name="arrowRight" size={16} color={colors.ink} strokeWidth={2.2} />
      </View>
    </Press>
  );
}

/** Underlined text link with a blue underline ("Skip to final draft"). */
export function SkipLink({
  label,
  onPress,
  style,
}: {
  label: string;
  onPress: () => void;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <Press
      onPress={onPress}
      accessibilityLabel={label}
      style={[{ alignSelf: 'center', padding: 10 }, style]}
    >
      <Txt size={14.5} weight={600}>
        {label}
      </Txt>
      <View style={styles.underline} />
    </Press>
  );
}

/** White pill with a lavender outline ("Regenerate", "Edit", "Replace"). */
export function OutlinePill({
  label,
  onPress,
  height = 30,
  fontSize = 12.5,
  icon,
  spinning,
  disabled,
}: {
  label: string;
  onPress: () => void;
  height?: number;
  fontSize?: number;
  icon?: React.ReactNode;
  spinning?: boolean;
  disabled?: boolean;
}) {
  return (
    <Press
      onPress={onPress}
      disabled={disabled}
      accessibilityLabel={label}
      accessibilityState={{ busy: spinning }}
      style={[
        styles.outline,
        { height, borderRadius: height / 2, paddingHorizontal: height > 32 ? 13 : 12 },
      ]}
    >
      {icon}
      <Txt size={fontSize} weight={600}>
        {label}
      </Txt>
    </Press>
  );
}

/* ------------------------------------------------------------------ pills & chips */

export function Pill({
  label,
  bg,
  fg = colors.ink,
  height = 28,
  fontSize = 12.5,
  upper,
  style,
}: {
  label: string;
  bg: string;
  fg?: string;
  height?: number;
  fontSize?: number;
  upper?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <View style={[styles.pill, { backgroundColor: bg, height, borderRadius: height / 2 }, style]}>
      <Txt size={fontSize} weight={600} color={fg} upper={upper} ls={upper ? 0.04 : undefined}>
        {label}
      </Txt>
    </View>
  );
}

/* ------------------------------------------------------------------ chat bubbles */

export function UserBubble({ text, fontSize = 15 }: { text: string; fontSize?: number }) {
  return (
    <View style={styles.userRow}>
      <View style={styles.userBubble}>
        <Txt size={fontSize} lh={1.45}>
          {text}
        </Txt>
      </View>
    </View>
  );
}

/** The blue sparkle avatar Curo speaks with. */
export function CuroMark({ size = 28 }: { size?: number }) {
  return (
    <View style={[styles.mark, { width: size, height: size, borderRadius: size / 2 }]}>
      <Icon name="sparkle" size={Math.round(size * 0.46)} color={colors.white} />
    </View>
  );
}

export function CuroBubble({ text }: { text: string }) {
  return (
    <View style={styles.curoRow}>
      <CuroMark />
      <View style={styles.curoBubble}>
        <Txt size={14} lh={1.5}>
          {text}
        </Txt>
      </View>
    </View>
  );
}

/* ------------------------------------------------------------------ dots, radios, switch */

/** Carousel position dots: the current one stretches into a pill. */
export function Dots({
  count,
  index,
  onGo,
  activeWidth = 26,
  activeColor = colors.blue,
  idleColor = colors.lavender,
  hit = 24,
  label = (n: number) => `Show item ${n}`,
}: {
  count: number;
  index: number;
  onGo: (i: number) => void;
  activeWidth?: number;
  activeColor?: string;
  idleColor?: string;
  hit?: number;
  label?: (n: number) => string;
}) {
  return (
    <View style={styles.dots}>
      {Array.from({ length: count }, (_, i) => {
        const on = i === index;
        return (
          <Pressable
            key={i}
            onPress={() => onGo(i)}
            accessibilityRole="button"
            accessibilityLabel={label(i + 1)}
            style={{ width: hit, height: 24, alignItems: 'center', justifyContent: 'center' }}
          >
            <Animated.View
              style={[
                {
                  height: 8,
                  borderRadius: 4,
                  width: on ? activeWidth : 8,
                  backgroundColor: on ? activeColor : idleColor,
                },
                springOn('width', 'backgroundColor'),
              ]}
            />
          </Pressable>
        );
      })}
    </View>
  );
}

/** Single-choice chips (audience toggle, DNA tabs). Selected = ink, others = grey or white. */
export function ChoiceChips<T extends string>({
  options,
  value,
  onChange,
  height = 42,
  fontSize = 14,
  idle = colors.gray,
  role = 'radio',
  gap = 8,
  center,
}: {
  options: { id: T; label: string }[];
  value: T;
  onChange: (id: T) => void;
  height?: number;
  fontSize?: number;
  idle?: string;
  role?: 'radio' | 'tab';
  gap?: number;
  center?: boolean;
}) {
  return (
    <View
      accessibilityRole={role === 'radio' ? 'radiogroup' : 'tablist'}
      style={{
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap,
        justifyContent: center ? 'center' : 'flex-start',
      }}
    >
      {options.map((o) => {
        const on = o.id === value;
        return (
          <Press
            key={o.id}
            onPress={() => onChange(o.id)}
            accessibilityRole={role}
            accessibilityLabel={o.label}
            accessibilityState={{ selected: on, checked: role === 'radio' ? on : undefined }}
            transform={[{ scale: on ? 1.04 : 1 }]}
            style={{
              height,
              paddingHorizontal: height >= 42 ? 18 : 14,
              borderRadius: height / 2,
              justifyContent: 'center',
              backgroundColor: on ? colors.ink : idle,
            }}
          >
            <Txt size={fontSize} weight={on ? 600 : 400} color={on ? colors.white : colors.ink}>
              {o.label}
            </Txt>
          </Press>
        );
      })}
    </View>
  );
}

export function Switch({ on }: { on: boolean }) {
  return (
    <Animated.View
      style={[
        styles.track,
        { backgroundColor: on ? colors.blue : colors.gray },
        springOn('backgroundColor'),
      ]}
    >
      <Animated.View
        style={[styles.knob, { transform: [{ translateX: on ? 18 : 0 }] }, springOn('transform')]}
      />
    </Animated.View>
  );
}

/* ------------------------------------------------------------------ metrics */

export type MetricKind = 'views' | 'likes' | 'shares' | 'comments';

/**
 * One public metric beside the reel: icon, value and the change pill.
 * `value` null = not public (hidden likes, no share count, comments off): shown as "–".
 * `change` null = nothing to compare with; |change| < 5 shows a flat dash (logic doc §6).
 */
export function Metric({
  kind,
  value,
  change,
}: {
  kind: MetricKind;
  value: string | null;
  change: number | null;
}) {
  const flat = change != null && Math.abs(change) < 5;
  const up = change != null && change >= 5;
  return (
    <View style={styles.metric}>
      <View style={{ height: 24, justifyContent: 'center' }}>
        <Icon name={kind} size={23} strokeWidth={1.5} />
      </View>
      <Txt size={17} weight={600}>
        {value ?? '–'}
      </Txt>
      {value != null && change != null ? (
        <View
          style={[
            styles.change,
            { backgroundColor: flat ? colors.gray : up ? colors.lavender : colors.pink },
          ]}
        >
          {flat ? null : (
            <Icon name={up ? 'arrowUpRight' : 'arrowDown'} size={11} strokeWidth={2.6} />
          )}
          <Txt size={11.5} weight={600}>
            {flat ? '–' : `${Math.abs(change)}%`}
          </Txt>
        </View>
      ) : (
        <View style={{ height: 19 }} />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  primary: {
    backgroundColor: colors.blue,
    flexDirection: 'row',
    alignItems: 'center',
    paddingRight: 6,
  },
  primaryCircle: { backgroundColor: colors.white, alignItems: 'center', justifyContent: 'center' },
  center: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10 },
  dark: {
    alignSelf: 'flex-start',
    height: 44,
    paddingLeft: 18,
    paddingRight: 5,
    borderRadius: 22,
    backgroundColor: colors.ink,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  darkCircle: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
  },
  underline: { height: 1.5, backgroundColor: colors.blue, marginTop: 3, borderRadius: 1 },
  outline: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderWidth: 1.5,
    borderColor: colors.lavender,
    backgroundColor: colors.white,
  },
  pill: { alignSelf: 'flex-start', paddingHorizontal: 12, justifyContent: 'center' },
  userRow: { flexDirection: 'row', justifyContent: 'flex-end' },
  userBubble: {
    maxWidth: '78%',
    backgroundColor: colors.lavender,
    borderTopLeftRadius: 22,
    borderTopRightRadius: 22,
    borderBottomRightRadius: 6,
    borderBottomLeftRadius: 22,
    paddingVertical: 10,
    paddingHorizontal: 16,
  },
  curoRow: { flexDirection: 'row', gap: 8, alignItems: 'flex-end' },
  mark: { backgroundColor: colors.blue, alignItems: 'center', justifyContent: 'center' },
  curoBubble: {
    maxWidth: '82%',
    backgroundColor: colors.gray,
    borderTopLeftRadius: 22,
    borderTopRightRadius: 22,
    borderBottomRightRadius: 22,
    borderBottomLeftRadius: 6,
    paddingVertical: 10,
    paddingHorizontal: 14,
  },
  dots: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center' },
  track: { width: 46, height: 28, borderRadius: 14, padding: 3 },
  knob: { width: 22, height: 22, borderRadius: 11, backgroundColor: colors.white },
  metric: { alignItems: 'center', gap: 4 },
  change: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    paddingVertical: 2,
    paddingLeft: 5,
    paddingRight: 7,
    borderRadius: 10,
  },
});
