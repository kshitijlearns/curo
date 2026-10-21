import type { TextStyle, ViewStyle } from 'react-native';
import { cubicBezier, type CSSAnimationProperties } from 'react-native-reanimated';

/**
 * A Reanimated CSS animation as a style.
 *
 * Expo's web typings (expo/types/react-native-web.d.ts) declare `animationTimingFunction`
 * on ViewStyle as a string, which clashes with Reanimated's `cubicBezier()`. The input is
 * checked against Reanimated's own type; only the hand-off to `style` is widened.
 */
export function cssAnimation(props: CSSAnimationProperties): ViewStyle {
  return props as unknown as ViewStyle;
}

/**
 * The prototype's motion, as Reanimated CSS timing functions.
 *
 * - `spring`: cubic-bezier(.2,.8,.3,1.25) — the springy overshoot used by the nav circle,
 *   pills, chips, cards and the `.pop` / `.rise` entrances (380 ms for transitions).
 * - `enter`: cubic-bezier(.2,.7,.2,1) — the `.ani` slide-up entrance (450 ms).
 * - `settle`: cubic-bezier(.2,.8,.3,1) — score arcs and carousels.
 */
export const EASE = {
  spring: cubicBezier(0.2, 0.8, 0.3, 1.25),
  enter: cubicBezier(0.2, 0.7, 0.2, 1),
  settle: cubicBezier(0.2, 0.8, 0.3, 1),
  bars: cubicBezier(0.2, 0.8, 0.3, 1.1),
} as const;

export const SPRING_MS = 380;

/** Style fragment: animate these properties with the springy curve (the `.spring` class). */
export function springOn(...props: (keyof ViewStyle | keyof TextStyle)[]) {
  return {
    transitionProperty: props as (keyof ViewStyle)[],
    transitionDuration: SPRING_MS,
    transitionTimingFunction: EASE.spring,
  } as const;
}
