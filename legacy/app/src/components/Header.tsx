import { StyleSheet, View } from 'react-native';

import { Icon } from './Icon';
import { Appear, Press } from './motion';
import { Txt } from './Txt';
import { Dots } from './ui';
import { colors } from '@/theme';

/**
 * The fixed lavender header. It extends 32px under the white sheet (which overlaps it with
 * its rounded top), so its bottom padding is larger than its top.
 */
export function BrandHeader({
  topInset,
  savedCount,
  onSaved,
  initial,
  onProfile,
}: {
  topInset: number;
  savedCount: number;
  onSaved: () => void;
  /** First letter of the creator's handle, shown on the profile button (D17). */
  initial?: string;
  onProfile?: () => void;
}) {
  return (
    <View style={[styles.brand, { paddingTop: 22 + topInset }]}>
      <Txt size={34} weight={600} ls={-0.02} style={{ lineHeight: 36 }}>
        Curo
      </Txt>
      <View style={styles.actions}>
        <Press
          onPress={onSaved}
          accessibilityLabel="Saved opportunities and drafts"
          style={styles.savedBtn}
        >
          <Icon name="bookmark" size={20} />
          {savedCount > 0 ? (
            <Appear kind="pop" key={savedCount} style={styles.badge}>
              <Txt size={11} weight={600} color={colors.white}>
                {savedCount}
              </Txt>
            </Appear>
          ) : null}
        </Press>
        {onProfile ? (
          <Press
            onPress={onProfile}
            accessibilityLabel="Account and settings"
            style={styles.profileBtn}
          >
            <Txt size={17} weight={600} color={colors.white}>
              {(initial ?? '').slice(0, 1).toUpperCase() || '·'}
            </Txt>
          </Press>
        ) : null}
      </View>
    </View>
  );
}

type BackHeaderProps = {
  topInset: number;
  title: string;
  onBack: () => void;
  sub?: string;
  bookmark?: { saved: boolean; onToggle: () => void };
  dots?: { count: number; index: number; onGo: (i: number) => void };
};

export function BackHeader({ topInset, title, onBack, sub, bookmark, dots }: BackHeaderProps) {
  return (
    <View style={[styles.back, { paddingTop: 20 + topInset }]}>
      <View style={styles.row}>
        <Press onPress={onBack} accessibilityLabel="Back" style={styles.circle44}>
          <Icon name="back" size={20} strokeWidth={1.8} />
        </Press>
        <Txt size={19} weight={600} align="center" style={{ flex: 1 }} numberOfLines={1}>
          {title}
        </Txt>
        {bookmark ? (
          <Press
            onPress={bookmark.onToggle}
            accessibilityLabel={bookmark.saved ? 'Remove from saved' : 'Save for later'}
            accessibilityState={{ selected: bookmark.saved }}
            transform={[{ scale: bookmark.saved ? 1.08 : 1 }]}
            style={[
              styles.circle44,
              { backgroundColor: bookmark.saved ? colors.blue : colors.white },
            ]}
          >
            <Icon
              name="bookmark"
              size={18}
              strokeWidth={1.8}
              filled={bookmark.saved}
              color={bookmark.saved ? colors.white : colors.ink}
            />
          </Press>
        ) : (
          <View style={{ width: 44 }} />
        )}
      </View>
      {sub ? (
        <Appear kind="fade" key={sub}>
          <Txt size={16} weight={300} align="center" style={{ marginTop: 12 }} numberOfLines={2}>
            {sub}
          </Txt>
        </Appear>
      ) : null}
      {dots ? (
        <View style={styles.dotsRow}>
          <Dots
            count={dots.count}
            index={dots.index}
            onGo={dots.onGo}
            activeWidth={22}
            idleColor={colors.white}
            hit={22}
            label={(n) => `Opportunity ${n}`}
          />
          <Txt size={12.5} style={{ marginLeft: 6 }}>
            {dots.index + 1} of {dots.count}
          </Txt>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  brand: {
    backgroundColor: colors.lavender,
    paddingHorizontal: 20,
    paddingBottom: 52,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  actions: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  savedBtn: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
  },
  profileBtn: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: colors.blue,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badge: {
    position: 'absolute',
    top: -2,
    right: -2,
    minWidth: 20,
    height: 20,
    paddingHorizontal: 5,
    borderRadius: 10,
    backgroundColor: colors.blue,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: colors.lavender,
  },
  back: { backgroundColor: colors.lavender, paddingHorizontal: 20, paddingBottom: 50 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  circle44: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dotsRow: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', marginTop: 10 },
});
