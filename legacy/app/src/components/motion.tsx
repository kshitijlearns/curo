/**
 * The prototype's CSS motion classes, ported with Reanimated's CSS animations:
 *
 *   .ani   slide up 12px + fade, 450 ms        <Appear kind="ani">
 *   .fade  fade, 350 ms                        <Appear kind="fade">
 *   .pop   scale .82 → 1 + fade, springy       <Appear kind="pop">
 *   .rise  up 10px, scale .9 → 1, springy      <Appear kind="rise">
 *   .skel  pulsing placeholder                 <Skeleton>
 *   .spin  rotating                            <Spin>
 *   .press scale .96 while pressed             <Press>
 */
import { useState } from 'react';
import { Pressable, type PressableProps, type StyleProp, type ViewStyle } from 'react-native';
import Animated, { type CSSAnimationKeyframes } from 'react-native-reanimated';

import { colors, cssAnimation, EASE, springOn } from '@/theme';

const KEYFRAMES: Record<'ani' | 'fade' | 'pop' | 'rise', CSSAnimationKeyframes> = {
  ani: {
    from: { opacity: 0, transform: [{ translateY: 12 }] },
    to: { opacity: 1, transform: [{ translateY: 0 }] },
  },
  fade: { from: { opacity: 0 }, to: { opacity: 1 } },
  pop: {
    from: { opacity: 0, transform: [{ scale: 0.82 }] },
    to: { opacity: 1, transform: [{ scale: 1 }] },
  },
  rise: {
    from: { opacity: 0, transform: [{ translateY: 10 }, { scale: 0.9 }] },
    to: { opacity: 1, transform: [{ translateY: 0 }, { scale: 1 }] },
  },
};

const TIMING = {
  ani: { animationDuration: 450, animationTimingFunction: EASE.enter },
  fade: { animationDuration: 350, animationTimingFunction: 'ease' as const },
  pop: { animationDuration: 450, animationTimingFunction: EASE.spring },
  rise: { animationDuration: 500, animationTimingFunction: EASE.spring },
};

type AppearProps = {
  kind?: keyof typeof KEYFRAMES;
  delay?: number;
  style?: StyleProp<ViewStyle>;
  children?: React.ReactNode;
};

/** Plays an entrance animation once, when it mounts. */
export function Appear({ kind = 'ani', delay = 0, style, children }: AppearProps) {
  return (
    <Animated.View
      style={[
        cssAnimation({
          animationName: KEYFRAMES[kind],
          ...TIMING[kind],
          animationDelay: delay,
          animationFillMode: 'both',
        }),
        style,
      ]}
    >
      {children}
    </Animated.View>
  );
}

type PressProps = Omit<PressableProps, 'style' | 'children'> & {
  style?: StyleProp<ViewStyle>;
  children?: React.ReactNode;
  /**
   * The element's own transform (lift, scale…), animated with the springy curve.
   * Like the prototype, elements with their own transform don't shrink when pressed.
   */
  transform?: ViewStyle['transform'];
  /** Scale while pressed (prototype `.press:active`). */
  pressedScale?: number;
};

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

/**
 * A pressable that springs: scale .96 while pressed, or its own transform. The Pressable
 * itself is the animated element, so layout styles (flex, alignSelf, margins) apply to it
 * directly in its parent.
 */
export function Press({
  style,
  children,
  transform,
  pressedScale = 0.96,
  disabled,
  onPressIn,
  onPressOut,
  ...rest
}: PressProps) {
  const [pressed, setPressed] = useState(false);
  const own = transform ?? [{ scale: pressed && !disabled ? pressedScale : 1 }];
  return (
    <AnimatedPressable
      accessibilityRole="button"
      disabled={disabled}
      // React Native Web reads selection from aria-selected, not accessibilityState.
      aria-selected={rest.accessibilityState?.selected}
      {...rest}
      onPressIn={(e) => {
        setPressed(true);
        onPressIn?.(e);
      }}
      onPressOut={(e) => {
        setPressed(false);
        onPressOut?.(e);
      }}
      style={[
        style,
        { transform: own },
        springOn('transform', 'opacity', 'backgroundColor', 'borderColor'),
      ]}
    >
      {children}
    </AnimatedPressable>
  );
}

const SKEL: CSSAnimationKeyframes = {
  '0%': { opacity: 1 },
  '50%': { opacity: 0.45 },
  '100%': { opacity: 1 },
};

/** Grey placeholder that pulses while content loads. */
export function Skeleton({ style, delay = 0 }: { style?: StyleProp<ViewStyle>; delay?: number }) {
  return (
    <Animated.View
      style={[
        {
          backgroundColor: colors.gray,
          animationName: SKEL,
          animationDuration: 1300,
          animationTimingFunction: 'ease-in-out',
          animationIterationCount: 'infinite',
          animationDelay: delay,
        },
        style,
      ]}
    />
  );
}

const SPIN: CSSAnimationKeyframes = {
  from: { transform: [{ rotate: '0deg' }] },
  to: { transform: [{ rotate: '360deg' }] },
};

/** Rotates its children forever (loading rings, the regenerate icon). */
export function Spin({
  children,
  active = true,
  style,
}: {
  children: React.ReactNode;
  active?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <Animated.View
      style={[
        active
          ? {
              animationName: SPIN,
              animationDuration: 900,
              animationTimingFunction: 'linear',
              animationIterationCount: 'infinite',
            }
          : null,
        style,
      ]}
    >
      {children}
    </Animated.View>
  );
}

const DOT: CSSAnimationKeyframes = {
  '0%': { opacity: 0.25, transform: [{ translateY: 0 }] },
  '40%': { opacity: 1, transform: [{ translateY: -3 }] },
  '80%': { opacity: 0.25, transform: [{ translateY: 0 }] },
  '100%': { opacity: 0.25, transform: [{ translateY: 0 }] },
};

/** Three bouncing dots while Curo is typing. */
export function TypingDots() {
  return (
    <Animated.View
      style={{ flexDirection: 'row', gap: 5, paddingVertical: 6, paddingHorizontal: 4 }}
    >
      {[0, 200, 400].map((delay) => (
        <Animated.View
          key={delay}
          style={{
            width: 7,
            height: 7,
            borderRadius: 4,
            backgroundColor: colors.blue,
            animationName: DOT,
            animationDuration: 1200,
            animationDelay: delay,
            animationIterationCount: 'infinite',
          }}
        />
      ))}
    </Animated.View>
  );
}
