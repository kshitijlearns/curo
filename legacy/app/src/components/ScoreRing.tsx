import { useEffect } from 'react';
import { View } from 'react-native';
import Animated, {
  Easing,
  useAnimatedProps,
  useSharedValue,
  withDelay,
  withTiming,
} from 'react-native-reanimated';
import Svg, { Circle, G } from 'react-native-svg';

import { colors } from '@/theme';

const AnimatedCircle = Animated.createAnimatedComponent(Circle);
const R = 62; // in the prototype's 140 × 140 viewBox
const C = 2 * Math.PI * R; // 389.6

type Props = {
  /** 0–1 share of the ring to fill. */
  progress: number;
  size: number;
  /** ms for the arc to sweep to a new value (it starts empty on mount). */
  duration?: number;
  delay?: number;
  children?: React.ReactNode;
};

/** Circular score: grey track, blue arc sweeping in from empty (opportunity and Simulator scores). */
export function ScoreRing({ progress, size, duration = 900, delay = 0, children }: Props) {
  const p = useSharedValue(0);
  useEffect(() => {
    p.value = withDelay(
      delay,
      withTiming(Math.max(0, Math.min(1, progress)), {
        duration,
        easing: Easing.bezier(0.2, 0.8, 0.3, 1),
      }),
    );
  }, [progress, duration, delay, p]);
  const arc = useAnimatedProps(() => ({ strokeDashoffset: C * (1 - p.value) }));

  return (
    <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={size} height={size} viewBox="0 0 140 140" style={{ position: 'absolute' }}>
        <G transform="rotate(-90 70 70)">
          <Circle cx={70} cy={70} r={R} fill="none" stroke={colors.gray} strokeWidth={8} />
          <AnimatedCircle
            cx={70}
            cy={70}
            r={R}
            fill="none"
            stroke={colors.blue}
            strokeWidth={8}
            strokeLinecap="round"
            strokeDasharray={`${C} ${C}`}
            animatedProps={arc}
          />
        </G>
      </Svg>
      {children}
    </View>
  );
}
