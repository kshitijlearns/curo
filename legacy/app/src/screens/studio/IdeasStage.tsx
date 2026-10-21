import { Pressable, StyleSheet, View } from 'react-native';
import Animated from 'react-native-reanimated';

import { useStudio } from './derived';
import { Icon } from '@/components/Icon';
import { Appear, Press, Skeleton, Spin } from '@/components/motion';
import { Eyebrow, Txt } from '@/components/Txt';
import { Pill, PrimaryButton, UserBubble } from '@/components/ui';
import type { IdeaOut } from '@/api/studio';
import { PART_LABELS, PART_ORDER, SLOT_LABELS } from '@/lib/studioText';
import { useApp } from '@/state/app';
import { colors, springOn } from '@/theme';

/** Studio step 1: three ideas (and a new round of three for each note the creator sends). */
export function IdeasStage() {
  const { st, project, oppLabel } = useStudio();
  const pickIdea = useApp((s) => s.pickIdea);
  const continueIdea = useApp((s) => s.continueIdea);
  const rounds = project?.rounds ?? [];
  const firstLoading = !rounds.length && st.busy === 'ideas';

  return (
    <Appear style={{ gap: 12 }}>
      {project?.opportunity || st.oppName ? (
        <View style={styles.oppCard}>
          <Eyebrow>Opportunity area</Eyebrow>
          <Txt size={21} weight={600} ls={-0.01}>
            {oppLabel}
          </Txt>
        </View>
      ) : null}

      {firstLoading ? <RoundHead prompt={null} loading /> : null}
      {firstLoading ? <Skeletons /> : null}

      {rounds.map((round) => (
        <View key={round.round} style={{ gap: 10 }}>
          {round.prompt ? (
            <Appear style={{ marginTop: 8 }}>
              <UserBubble text={round.prompt} />
            </Appear>
          ) : null}
          <RoundHead prompt={round.prompt ?? null} loading={false} />
          {round.ideas.map((idea, ii) => (
            <IdeaCard
              key={idea.id}
              testID={`idea-${round.round}-${ii}`}
              idea={idea}
              delay={ii * 80}
              selected={st.pick === idea.id}
              whyOpen={st.openWhy === idea.id}
              onPick={() => pickIdea(idea.id)}
            />
          ))}
        </View>
      ))}

      {st.pendingRound ? (
        <View style={{ gap: 10 }}>
          <Appear style={{ marginTop: 8 }}>
            <UserBubble text={st.pendingRound} />
          </Appear>
          <RoundHead prompt={st.pendingRound} loading />
          <Skeletons />
        </View>
      ) : null}

      {st.pick ? (
        <Appear kind="rise" style={{ marginTop: 4 }}>
          <PrimaryButton label="Develop this idea" onPress={continueIdea} disabled={!!st.busy} />
        </Appear>
      ) : null}
    </Appear>
  );
}

function RoundHead({ prompt, loading }: { prompt: string | null; loading: boolean }) {
  return (
    <View style={styles.label}>
      <Spin active={loading}>
        <View style={styles.mark}>
          <Icon name="sparkle" size={12} color={colors.white} />
        </View>
      </Spin>
      <Txt size={13} weight={600}>
        {loading ? 'Thinking…' : prompt ? 'Three new directions from your note' : 'Curo suggests'}
      </Txt>
    </View>
  );
}

function Skeletons() {
  return (
    <View style={{ gap: 10 }}>
      {[0, 150, 300].map((d) => (
        <Skeleton key={d} delay={d} style={{ height: 78, borderRadius: 22 }} />
      ))}
    </View>
  );
}

function IdeaCard({
  testID,
  idea,
  delay,
  selected,
  whyOpen,
  onPick,
}: {
  testID: string;
  idea: IdeaOut;
  delay: number;
  selected: boolean;
  whyOpen: boolean;
  onPick: () => void;
}) {
  const toggleWhy = useApp((s) => s.toggleWhy);
  // The card's pressable area and the "Why this idea?" toggle are siblings: nesting one
  // control inside another breaks accessibility (and is invalid HTML on web).
  return (
    <Appear delay={delay}>
      <Animated.View
        style={[
          styles.card,
          {
            borderColor: selected ? colors.blue : colors.gray,
            backgroundColor: selected ? colors.pink : colors.white,
            transform: [{ translateY: selected ? -3 : 0 }],
          },
          springOn('transform', 'backgroundColor', 'borderColor'),
        ]}
      >
        <Press
          testID={testID}
          onPress={onPick}
          accessibilityLabel={idea.text}
          accessibilityState={{ selected }}
          style={styles.cardMain}
        >
          <View style={{ flex: 1, gap: 6 }}>
            <Txt size={16.5} weight={600} lh={1.4}>
              {idea.text}
            </Txt>
            <Txt size={13} lh={1.5} color={colors.muted}>
              {idea.why}
            </Txt>
          </View>
          <Animated.View
            style={[
              styles.radio,
              {
                borderColor: selected ? colors.blue : colors.lavender,
                backgroundColor: selected ? colors.blue : 'rgba(91,115,242,0)',
                transform: [{ scale: selected ? 1.12 : 1 }],
              },
              springOn('backgroundColor', 'borderColor', 'transform'),
            ]}
          >
            {selected ? (
              <Appear kind="pop">
                <Icon name="check" size={12} strokeWidth={3} color={colors.white} />
              </Appear>
            ) : null}
          </Animated.View>
        </Press>
        <Pressable
          onPress={() => toggleWhy(idea.id)}
          accessibilityRole="button"
          accessibilityState={{ expanded: whyOpen }}
          hitSlop={8}
          style={{ alignSelf: 'flex-start', marginTop: 6 }}
        >
          <Txt
            size={13}
            weight={600}
            color={colors.blue}
            style={{ textDecorationLine: 'underline' }}
          >
            {whyOpen ? 'Hide' : 'Why this idea?'}
          </Txt>
        </Pressable>
        {whyOpen ? <WhyThisIdea idea={idea} /> : null}
      </Animated.View>
    </Appear>
  );
}

/**
 * "Why this idea" (logic doc §9): each part's share of the ranking score, w·s / Σ w·s,
 * plus the evidence behind the idea. The model doesn't mix data in fixed percentages,
 * so the panel says these are shares of Curo's score.
 */
function WhyThisIdea({ idea }: { idea: IdeaOut }) {
  const shares = idea.shares;
  return (
    <Appear kind="fade" style={styles.why}>
      {idea.slot ? (
        <Pill label={SLOT_LABELS[idea.slot]} bg={colors.white} height={24} fontSize={12} />
      ) : null}
      {shares
        ? PART_ORDER.map((k) => (
            <View key={k} style={styles.shareRow}>
              <Txt size={12.5} style={{ width: 84 }}>
                {PART_LABELS[k]}
              </Txt>
              <View style={styles.shareTrack}>
                <View style={[styles.shareFill, { width: `${shares[k]}%` }]} />
              </View>
              <Txt size={12.5} weight={600} tabular style={{ width: 36, textAlign: 'right' }}>
                {shares[k]}%
              </Txt>
            </View>
          ))
        : null}
      <Txt size={12} lh={1.5} color={colors.muted}>
        Each part’s share of Curo’s ranking score for this idea, not a mix of data.
      </Txt>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
        {(idea.evidence ?? []).map((e) => (
          <View key={e} style={styles.chip}>
            <Txt size={12} lh={1.35}>
              {e}
            </Txt>
          </View>
        ))}
      </View>
    </Appear>
  );
}

const styles = StyleSheet.create({
  oppCard: {
    backgroundColor: colors.pink,
    borderRadius: 24,
    paddingVertical: 16,
    paddingHorizontal: 18,
    gap: 4,
  },
  label: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 },
  mark: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.blue,
    alignItems: 'center',
    justifyContent: 'center',
  },
  card: {
    borderWidth: 1.5,
    borderRadius: 22,
    paddingVertical: 16,
    paddingLeft: 18,
    paddingRight: 16,
  },
  cardMain: { flexDirection: 'row', gap: 14, alignItems: 'flex-start' },
  radio: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  why: { gap: 8, marginTop: 4, padding: 12, borderRadius: 18, backgroundColor: colors.gray },
  shareRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  shareTrack: {
    flex: 1,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.white,
    overflow: 'hidden',
  },
  shareFill: { height: 6, borderRadius: 3, backgroundColor: colors.blue },
  chip: {
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: 11,
    backgroundColor: colors.white,
  },
});
