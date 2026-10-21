import { Pressable, StyleSheet, View } from 'react-native';
import Animated from 'react-native-reanimated';

import { Icon, type IconName } from './Icon';
import { Txt } from './Txt';
import { colors, springOn } from '@/theme';

export type Tab = 'home' | 'studio' | 'sim';

const ITEMS: { id: Tab; label: string; icon: IconName }[] = [
  { id: 'home', label: 'Home', icon: 'home' },
  { id: 'studio', label: 'Studio', icon: 'studio' },
  { id: 'sim', label: 'Simulator', icon: 'simulator' },
];

/**
 * Bottom navigation. The active tab's icon grows into a 52px blue circle that springs up
 * 30px out of the bar, wrapped in a white ring with a grey outline (prototype Nav).
 */
export function Nav({
  active,
  onNav,
  bottomInset = 0,
}: {
  active: Tab;
  onNav: (tab: Tab) => void;
  bottomInset?: number;
}) {
  return (
    <View style={[styles.outer, { paddingBottom: 14 + bottomInset }]}>
      <View style={styles.bar} accessibilityRole="tablist">
        {ITEMS.map((it) => {
          const on = it.id === active;
          return (
            <Pressable
              key={it.id}
              onPress={() => onNav(it.id)}
              accessibilityRole="tab"
              accessibilityLabel={it.label}
              accessibilityState={{ selected: on }}
              style={styles.item}
            >
              {/* Layout box; ring, blue fill and icon are stacked inside in paint order. */}
              <Animated.View
                style={[
                  styles.circle,
                  { width: on ? 52 : 32, height: on ? 52 : 32, marginTop: on ? -30 : 0 },
                  springOn('width', 'height', 'marginTop'),
                ]}
              >
                <Animated.View
                  pointerEvents="none"
                  style={[styles.ring, { opacity: on ? 1 : 0 }, springOn('opacity')]}
                />
                <Animated.View
                  pointerEvents="none"
                  style={[
                    styles.fill,
                    { backgroundColor: on ? colors.blue : 'rgba(91,115,242,0)' },
                    springOn('backgroundColor'),
                  ]}
                />
                {/* Own view so it stacks above the absolute fill on every platform. */}
                <View>
                  <Icon
                    name={it.icon}
                    size={22}
                    color={on ? colors.white : colors.muted}
                    strokeWidth={it.id === 'sim' ? 1.8 : 1.7}
                  />
                </View>
              </Animated.View>
              <Txt
                size={12}
                weight={on ? 600 : 400}
                color={on ? colors.ink : colors.muted}
                ls={0.01}
              >
                {it.label}
              </Txt>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  outer: { paddingHorizontal: 16 },
  bar: {
    flexDirection: 'row',
    // The prototype's CSS is content-box: 68 content + 9 bottom padding + 2 border = 79.
    height: 79,
    alignItems: 'flex-end',
    paddingHorizontal: 10,
    paddingBottom: 9,
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.gray,
    borderRadius: 34,
  },
  item: { flex: 1, alignItems: 'center', justifyContent: 'flex-end', gap: 3 },
  circle: { alignItems: 'center', justifyContent: 'center' },
  // box-shadow: 0 0 0 6px #fff, 0 0 0 7px #E4E4EC — outside the circle's box, so no layout effect.
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
  fill: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, borderRadius: 999 },
});
