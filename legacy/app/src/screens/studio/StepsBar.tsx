import { Pressable, StyleSheet, View } from 'react-native';
import Animated from 'react-native-reanimated';

import { Icon } from '@/components/Icon';
import { Appear } from '@/components/motion';
import { Txt } from '@/components/Txt';
import { useApp } from '@/state/app';
import { colors, springOn } from '@/theme';

const LABELS = ['Idea', 'Script', 'Visuals', 'Caption', 'Final'];
const STAGE_INDEX = { ideas: 0, idea: 1, script: 1, storyboard: 2, caption: 3, final: 4 } as const;

/** Studio's five steps. The current step lifts in a blue circle; done steps show a tick. */
export function StepsBar() {
  const st = useApp((s) => s.studio);
  const goStep = useApp((s) => s.goStep);
  const stageIdx = STAGE_INDEX[st.stage];

  return (
    <View style={styles.row} accessibilityRole="tablist" accessibilityLabel="Studio steps">
      {LABELS.map((label, i) => {
        const cur = i === stageIdx;
        const reach = i <= st.maxStep;
        const done = !cur && (i < st.maxStep || i < stageIdx);
        return (
          <Pressable
            key={label}
            onPress={() => goStep(i)}
            disabled={!reach && !cur}
            accessibilityRole="tab"
            accessibilityLabel={label}
            accessibilityState={{ selected: cur, disabled: !reach && !cur }}
            style={styles.item}
          >
            <Animated.View
              style={[
                styles.circle,
                {
                  transform: [{ translateY: cur ? -6 : 0 }, { scale: cur ? 1.06 : 1 }],
                },
                springOn('transform'),
              ]}
            >
              {cur ? <View style={styles.ring} /> : null}
              <Animated.View
                style={[
                  styles.fill,
                  {
                    backgroundColor: cur ? colors.blue : done ? colors.lavender : colors.white,
                    borderWidth: cur || done ? 0 : 1.5,
                    borderColor: reach ? colors.lavender : colors.gray,
                  },
                  springOn('backgroundColor'),
                ]}
              >
                {done ? (
                  <Appear kind="pop">
                    <Icon name="check" size={17} strokeWidth={2.4} color={colors.ink} />
                  </Appear>
                ) : (
                  <Txt
                    size={15}
                    weight={600}
                    color={cur ? colors.white : reach ? colors.ink : colors.muted}
                  >
                    {i + 1}
                  </Txt>
                )}
              </Animated.View>
            </Animated.View>
            <Txt
              size={12}
              weight={cur ? 600 : 400}
              color={cur || reach ? colors.ink : colors.muted}
            >
              {label}
            </Txt>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', paddingTop: 6 },
  item: { flex: 1, alignItems: 'center', gap: 6 },
  circle: { width: 46, height: 46 },
  // box-shadow: 0 0 0 6px #fff, 0 0 0 7px #E4E4EC
  ring: {
    position: 'absolute',
    top: -7,
    left: -7,
    right: -7,
    bottom: -7,
    borderRadius: 999,
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.gray,
  },
  fill: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    borderRadius: 23,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
