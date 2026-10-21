import { ScrollView, StyleSheet, View } from 'react-native';
import Animated from 'react-native-reanimated';

import { ReelCarousel } from './ReelCarousel';
import type { Schemas } from '@/api/client';
import { useInsights, useMe, useReels } from '@/api/hooks';
import { Icon } from '@/components/Icon';
import { Appear, Skeleton } from '@/components/motion';
import { Eyebrow, Txt } from '@/components/Txt';
import { Pill } from '@/components/ui';
import { updatedAgo } from '@/lib/format';
import { PHASES } from '@/mock/data';
import { useSheetScroll } from '@/screens/shell/useSheetScroll';
import { useApp } from '@/state/app';
import { colors, springOn } from '@/theme';

const ICON_BG = [colors.blue, colors.lavender, colors.pink];

/**
 * Insights for one reel (logic doc §7): where it is in its life, what the audience's
 * behaviour says, and what people are actually writing. Every number comes from the API;
 * thin data is said plainly in the notes under the phase.
 */
export function InsightsView() {
  const ref = useSheetScroll();
  const reels = useReels(10).data ?? [];
  const now = useMe().data?.now;
  const reel =
    reels[
      Math.min(
        useApp((s) => s.reelIdx),
        reels.length - 1,
      )
    ];
  const insights = useInsights(reel?.id);

  if (!reel) return null;
  const data = insights.data;
  const updated = updatedAgo(reel.lastSnapshotAt, now ? new Date(now) : undefined);

  return (
    <ScrollView
      ref={ref}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      <Appear kind="fade" style={{ gap: 16 }}>
        <ReelCarousel reels={reels} heightRatio={250 / 172} onInsights />

        {insights.isPending ? (
          <View style={{ gap: 16 }}>
            <Skeleton style={{ height: 230, borderRadius: 26 }} />
            <Skeleton style={{ height: 96, borderRadius: 22 }} />
            <Skeleton style={{ height: 96, borderRadius: 22 }} />
          </View>
        ) : insights.isError ? (
          <Txt size={14} lh={1.55} color={colors.muted}>
            Couldn’t load the insights: {insights.error.message}.
          </Txt>
        ) : data ? (
          <>
            <PhaseCard
              key={`phase-${reel.id}`}
              phase={data.phase}
              updated={updated}
              notes={data.notes ?? []}
            />

            {data.audience?.length ? (
              <>
                <Txt size={20} weight={600} style={{ marginTop: 8 }}>
                  What your audience thinks
                </Txt>
                {(data.audience ?? []).map((card, i) => (
                  <AudienceCard key={`${reel.id}-${card.key}`} card={card} index={i} />
                ))}
              </>
            ) : null}

            {data.top_comment ? <TopComment comment={data.top_comment} /> : null}
          </>
        ) : null}
      </Appear>
    </ScrollView>
  );
}

function PhaseCard({
  phase,
  updated,
  notes,
}: {
  phase: Schemas['PhaseOut'] | null | undefined;
  updated: string | null;
  notes: string[];
}) {
  const phaseIdx = phase ? PHASES.findIndex((p) => p.id === phase.id) : -1;
  return (
    <Appear style={styles.phaseCard}>
      <View style={styles.rowBetween}>
        <Txt size={18} weight={600}>
          Phase of reel
        </Txt>
        {phase?.usual_range ? (
          <Pill label={phase.usual_range} bg={colors.white} height={30} fontSize={13} />
        ) : null}
      </View>
      {phase ? (
        <>
          <Txt size={22} weight={300} style={{ marginTop: 6 }}>
            {phase.label}
            {phase.estimated ? ' (estimated)' : ''}
          </Txt>
          <Txt size={14.5} lh={1.55}>
            {phase.description}
          </Txt>
        </>
      ) : (
        <Txt size={14.5} lh={1.55} style={{ marginTop: 6 }}>
          Curo needs a first snapshot of this reel to place it.
        </Txt>
      )}
      {[updated, ...notes].filter(Boolean).map((line) => (
        <Txt key={line} size={12.5} lh={1.45} color={colors.muted}>
          {line}
        </Txt>
      ))}
      <View style={styles.track}>
        <View style={styles.trackLine} />
        {PHASES.map((p, i) => {
          const cur = i === phaseIdx;
          const past = phaseIdx >= 0 && i < phaseIdx;
          return (
            <View key={p.id} style={styles.step}>
              <View style={{ width: 42, height: 42 }}>
                {cur ? <View style={styles.stepRing} /> : null}
                <Animated.View
                  style={[
                    styles.stepDot,
                    {
                      backgroundColor: cur ? colors.blue : past ? colors.lavender : colors.white,
                      transform: [{ translateY: cur ? -4 : 0 }],
                    },
                    springOn('backgroundColor', 'transform'),
                  ]}
                >
                  <Txt size={13} weight={600} color={cur ? colors.white : colors.ink}>
                    {i + 1}
                  </Txt>
                </Animated.View>
              </View>
              <Txt size={12} weight={cur ? 600 : 400} align="center" numberOfLines={1}>
                {p.label}
              </Txt>
            </View>
          );
        })}
      </View>
    </Appear>
  );
}

function AudienceCard({ card, index }: { card: Schemas['AudienceCard']; index: number }) {
  return (
    <Appear delay={index * 80} style={styles.audCard}>
      <View style={[styles.audIcon, { backgroundColor: ICON_BG[index % 3] }]}>
        <Icon
          name={card.icon}
          size={18}
          strokeWidth={1.8}
          color={index === 0 ? colors.white : colors.ink}
        />
      </View>
      <View style={{ flex: 1, gap: 4 }}>
        <Txt size={15.5} weight={600} lh={1.3}>
          {card.title}
        </Txt>
        <Txt size={13.5} lh={1.55} color={colors.muted}>
          {card.text}
        </Txt>
      </View>
    </Appear>
  );
}

function TopComment({ comment }: { comment: Schemas['TopCommentOut'] }) {
  return (
    <View style={styles.topComment}>
      <Eyebrow color={colors.lavender}>Top comment says</Eyebrow>
      <View style={{ flexDirection: 'row', gap: 12, alignItems: 'flex-start' }}>
        <View style={styles.quote}>
          <Txt size={22} weight={600} style={{ lineHeight: 26, marginTop: 6 }}>
            “
          </Txt>
        </View>
        <View style={{ flex: 1, gap: 4 }}>
          {comment.negative ? (
            <Pill label="Critical" bg={colors.pink} height={22} fontSize={11.5} />
          ) : null}
          <Txt size={16} lh={1.45} weight={300} color={colors.white}>
            {comment.text}
          </Txt>
          <Txt size={12.5} color={colors.gray}>
            {comment.likes} likes · {comment.replies} replies
          </Txt>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: 20, paddingTop: 22, paddingBottom: 28 },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  phaseCard: {
    backgroundColor: colors.gray,
    borderRadius: 26,
    paddingTop: 20,
    paddingHorizontal: 18,
    paddingBottom: 18,
    gap: 6,
  },
  track: { flexDirection: 'row', marginTop: 16 },
  trackLine: {
    position: 'absolute',
    left: '10%',
    right: '10%',
    top: 21,
    height: 2,
    backgroundColor: colors.white,
  },
  step: { flex: 1, alignItems: 'center', gap: 6 },
  stepRing: {
    position: 'absolute',
    top: -9,
    left: -5,
    right: -5,
    bottom: -1,
    borderRadius: 999,
    backgroundColor: colors.white,
  },
  stepDot: {
    width: 42,
    height: 42,
    borderRadius: 21,
    alignItems: 'center',
    justifyContent: 'center',
  },
  audCard: {
    flexDirection: 'row',
    gap: 14,
    alignItems: 'flex-start',
    borderWidth: 1,
    borderColor: colors.gray,
    borderRadius: 22,
    padding: 16,
  },
  audIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  topComment: { backgroundColor: colors.ink, borderRadius: 24, padding: 18, gap: 12 },
  quote: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: colors.pink,
    alignItems: 'center',
  },
});
