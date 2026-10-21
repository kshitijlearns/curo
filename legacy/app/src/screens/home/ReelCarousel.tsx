import { useEffect, useRef } from 'react';
import { Linking, ScrollView, StyleSheet, useWindowDimensions, View } from 'react-native';

import { COMPARISON_NOTES, type ReelVM } from '@/api/reels';
import { Press } from '@/components/motion';
import { ReelThumb } from '@/components/ReelThumb';
import { Txt } from '@/components/Txt';
import { Dots, Metric } from '@/components/ui';
import { useApp } from '@/state/app';
import { colors } from '@/theme';

const GAP = 10;
const SIDE = 25;

/**
 * The reel carousel with the four public metrics either side (Home and Insights).
 * Layout from the prototype: 64 | carousel | 64 inside 20px gutters; on a 390-wide
 * screen the carousel is 222 wide with 172-wide cards.
 */
export function ReelCarousel({
  reels,
  heightRatio,
  onInsights,
}: {
  reels: ReelVM[];
  heightRatio: number;
  onInsights: boolean;
}) {
  const { width } = useWindowDimensions();
  const stored = useApp((s) => s.reelIdx);
  const goReel = useApp((s) => s.goReel);
  const openInsights = useApp((s) => s.openInsights);
  const scroller = useRef<ScrollView>(null);
  const reelIdx = Math.min(stored, Math.max(reels.length - 1, 0));
  const shown = useRef(reelIdx);

  const center = Math.max(180, width - 40 - 128);
  const cardW = center - SIDE * 2;
  const cardH = Math.round(cardW * heightRatio);
  const step = cardW + GAP;
  const metricGap = Math.max(24, Math.round(cardH * (64 / 270)));
  const reel = reels[reelIdx];

  // Follow dot taps and other index changes.
  useEffect(() => {
    if (shown.current === reelIdx) return;
    shown.current = reelIdx;
    scroller.current?.scrollTo({ x: reelIdx * step, animated: true });
  }, [reelIdx, step]);

  if (!reel) return null;

  const onSettle = (x: number) => {
    const i = Math.max(0, Math.min(reels.length - 1, Math.round(x / step)));
    if (i !== useApp.getState().reelIdx) {
      shown.current = i;
      goReel(i);
    }
  };

  return (
    <View>
      <View style={styles.row}>
        <View style={[styles.side, { gap: metricGap }]}>
          <Metric kind="views" {...reel.metrics.views} />
          <Metric kind="likes" {...reel.metrics.likes} />
        </View>
        <ScrollView
          ref={scroller}
          horizontal
          showsHorizontalScrollIndicator={false}
          snapToInterval={step}
          decelerationRate="fast"
          disableIntervalMomentum
          contentOffset={{ x: reelIdx * step, y: 0 }}
          onMomentumScrollEnd={(e) => onSettle(e.nativeEvent.contentOffset.x)}
          onScrollEndDrag={(e) => onSettle(e.nativeEvent.contentOffset.x)}
          style={{ width: center }}
          contentContainerStyle={{ paddingHorizontal: SIDE, paddingVertical: 8, gap: GAP }}
        >
          {reels.map((r, i) => {
            const cur = i === reelIdx;
            return (
              <Press
                key={r.id}
                onPress={
                  () =>
                    !cur ? goReel(i) : !onInsights ? openInsights(i) : Linking.openURL(r.permalink) // logic doc §6: the reel on Instagram
                }
                accessibilityLabel={
                  cur
                    ? onInsights
                      ? `Open ${r.title} on Instagram`
                      : `View insights for ${r.title}`
                    : `Show ${r.title}`
                }
                transform={[{ scale: cur ? 1 : 0.88 }]}
                style={{
                  width: cardW,
                  height: cardH,
                  borderRadius: 22,
                  overflow: 'hidden',
                  opacity: cur ? 1 : 0.5,
                }}
              >
                <ReelThumb
                  title={r.title}
                  tone={r.tone}
                  duration={r.duration}
                  height={cardH}
                  titleSize={17}
                />
              </Press>
            );
          })}
        </ScrollView>
        <View style={[styles.side, { gap: metricGap }]}>
          <Metric kind="shares" {...reel.metrics.shares} />
          <Metric kind="comments" {...reel.metrics.comments} />
        </View>
      </View>
      <View style={{ marginTop: 8 }}>
        <Dots count={reels.length} index={reelIdx} onGo={goReel} label={(n) => `Show reel ${n}`} />
      </View>
      <Txt size={12} color={colors.muted} align="center" lh={1.4} style={{ marginTop: 2 }}>
        {COMPARISON_NOTES[reel.comparedWith ?? 'none']}
      </Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', marginTop: 14 },
  side: { width: 64, alignItems: 'center' },
});
