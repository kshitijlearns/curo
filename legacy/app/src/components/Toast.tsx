import { StyleSheet } from 'react-native';
import Animated, { type CSSAnimationKeyframes } from 'react-native-reanimated';

import { Txt } from './Txt';
import { colors, cssAnimation, EASE } from '@/theme';

const IN: CSSAnimationKeyframes = {
  from: { opacity: 0, transform: [{ translateY: 14 }] },
  to: { opacity: 1, transform: [{ translateY: 0 }] },
};

/** Dark status message above the dock (prototype toast). Remount with a new key to replay. */
export function Toast({ message, bottom }: { message: string; bottom: number }) {
  return (
    <Animated.View
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
      pointerEvents="none"
      style={[
        styles.toast,
        { bottom },
        cssAnimation({
          animationName: IN,
          animationDuration: 400,
          animationTimingFunction: EASE.spring,
        }),
      ]}
    >
      <Txt size={14} lh={1.5} color={colors.white}>
        {message}
      </Txt>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  toast: {
    position: 'absolute',
    left: 30,
    right: 30,
    alignSelf: 'center',
    maxWidth: 330,
    backgroundColor: colors.ink,
    borderRadius: 20,
    paddingVertical: 14,
    paddingHorizontal: 16,
    zIndex: 5,
  },
});
