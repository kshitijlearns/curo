import { useEffect, useRef, useState } from 'react';
import { FlatList, ScrollView, StyleSheet, useWindowDimensions, View } from 'react-native';
import Animated from 'react-native-reanimated';

import type { Schemas } from '@/api/client';
import { useDismissOpportunity, useOpportunities, useOpportunity } from '@/api/hooks';
import { Icon } from '@/components/Icon';
import { Appear, Press, Skeleton } from '@/components/motion';
import { ScoreRing } from '@/components/ScoreRing';
import { Eyebrow, Txt } from '@/components/Txt';
import { Pill, PrimaryButton, SkipLink } from '@/components/ui';
import { useApp } from '@/state/app';
import { colors, EASE } from '@/theme';

const AVATAR_BG = [colors.lavender, colors.pink, colors.gray];

type Card = Schemas['OpportunityCard'];

/** The opportunity pages, swiped sideways in score order (logic doc §8, step 4). */
export function useOpportunityPages(): { pages: Card[]; index: number } {
  const opportunities = useOpportunities();
  const list = opportunities.data ?? [];
  const oppId = useApp((s) => s.oppId);
  // A saved opportunity outside today's top 5 still opens (from Saved).
  const outside = opportunities.isSuccess && oppId && !list.some((o) => o.id === oppId);
  const current = useOpportunity(outside ? oppId : undefined).data;
  const pages = current && !list.some((o) => o.id === current.id) ? [...list, current] : list;
  return {
    pages,
    index: Math.max(
      0,
      pages.findIndex((o) => o.id === oppId),
    ),
  };
}

export function OpportunityPager() {
  const { width } = useWindowDimensions();
  // Each page scrolls vertically, so it needs a bounded height: the pager's own.
  const [height, setHeight] = useState(0);
  const setOpp = useApp((s) => s.setOpp);
  const { pages, index } = useOpportunityPages();
  const list = useRef<FlatList<Card>>(null);
  const shown = useRef(index);

  useEffect(() => {
    if (shown.current === index) return;
    shown.current = index;
    list.current?.scrollToOffset({ offset: index * width, animated: true });
  }, [index, width]);

  const onSettle = (x: number) => {
    const i = Math.max(0, Math.min(pages.length - 1, Math.round(x / width)));
    if (pages[i] && pages[i].id !== useApp.getState().oppId) {
      shown.current = i;
      setOpp(pages[i].id);
    }
  };

  return (
    <Appear kind="fade" style={{ flex: 1 }}>
      <View style={{ flex: 1 }} onLayout={(e) => setHeight(e.nativeEvent.layout.height)}>
        {height > 0 && pages.length ? (
          <FlatList
            ref={list}
            data={pages}
            keyExtractor={(o) => o.id}
            horizontal
            pagingEnabled
            showsHorizontalScrollIndicator={false}
            initialScrollIndex={index}
            getItemLayout={(_, i) => ({ length: width, offset: width * i, index: i })}
            onMomentumScrollEnd={(e) => onSettle(e.nativeEvent.contentOffset.x)}
            style={{ flex: 1 }}
            renderItem={({ item, index: i }) => (
              <OpportunityPage
                id={item.id}
                current={i === index}
                next={pages[i + 1]}
                width={width}
                height={height}
              />
            )}
          />
        ) : null}
      </View>
    </Appear>
  );
}

function OpportunityPage({
  id,
  current,
  next,
  width,
  height,
}: {
  id: string;
  current: boolean;
  next?: Card;
  width: number;
  height: number;
}) {
  const openInStudio = useApp((s) => s.openInStudio);
  const setOpp = useApp((s) => s.setOpp);
  const goHomeRoot = useApp((s) => s.goHomeRoot);
  const showToast = useApp((s) => s.showToast);
  const dismiss = useDismissOpportunity();
  const detail = useOpportunity(id);
  const opp = detail.data;

  if (!opp) {
    return (
      <View style={[{ width, height }, styles.page]}>
        <Skeleton style={{ height: 132, width: 132, borderRadius: 66, alignSelf: 'center' }} />
        <Skeleton style={{ height: 120, borderRadius: 22 }} />
        <Skeleton style={{ height: 160, borderRadius: 26 }} />
      </View>
    );
  }
  const avatars = opp.competitor_handles.map((h, i) => ({
    initial: h.replace('@', '').charAt(0).toUpperCase(),
    bg: AVATAR_BG[i % 3],
  }));
  const more =
    opp.competitor_more > 0
      ? `and ${opp.competitor_more} more creator${opp.competitor_more === 1 ? '' : 's'} you track`
      : '';

  return (
    <ScrollView
      style={{ width, height }}
      contentContainerStyle={styles.page}
      showsVerticalScrollIndicator={false}
    >
      <View style={{ alignItems: 'center' }}>
        <Animated.View
          style={{
            transform: [{ scale: current ? 1 : 0.9 }],
            transitionProperty: 'transform',
            transitionDuration: 450,
            transitionTimingFunction: EASE.spring,
          }}
        >
          <ScoreRing progress={current ? opp.score / 10 : 0} size={132}>
            <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: 1 }}>
              <Txt size={50} weight={300} ls={-0.04} style={{ lineHeight: 54 }}>
                {opp.score_shown}
              </Txt>
              <Txt size={17} color={colors.muted}>
                /10
              </Txt>
            </View>
          </ScoreRing>
        </Animated.View>
        <View style={{ marginTop: 12 }}>
          <Eyebrow color={colors.muted}>Opportunity score</Eyebrow>
        </View>
      </View>

      <Txt size={25} weight={600} ls={-0.015} align="center" style={{ marginTop: 2 }}>
        {opp.name}
      </Txt>
      <Txt size={15} lh={1.6} align="center" color={colors.muted}>
        {opp.description}
      </Txt>
      <View style={styles.signals}>
        {opp.signals.map((s) => (
          <View key={s} style={styles.signal}>
            <Txt size={13}>{s}</Txt>
          </View>
        ))}
      </View>

      <View style={styles.dark}>
        <View style={{ flex: 1, gap: 10 }}>
          <Txt size={15.5} weight={600} lh={1.3} color={colors.white}>
            What your competitors are doing
          </Txt>
          {avatars.length ? (
            <View style={{ flexDirection: 'row' }}>
              {avatars.map((a, i) => (
                <View key={i} style={[styles.avatar, { backgroundColor: a.bg }]}>
                  <Txt size={14} weight={600}>
                    {a.initial}
                  </Txt>
                </View>
              ))}
            </View>
          ) : null}
          <Txt size={13} lh={1.5} color={colors.gray}>
            {opp.competitor_handles.length
              ? `${opp.competitor_handles.join(', ')}${more ? '\n' : ''}`
              : 'None of the creators you track has posted on it yet.'}
            {more ? (
              <Txt size={12} color={colors.lavender}>
                {more}
              </Txt>
            ) : null}
          </Txt>
        </View>
        <View style={styles.darkRight}>
          <Txt size={13.5} lh={1.6} weight={300} color={colors.white}>
            {opp.competitor_text}
          </Txt>
        </View>
      </View>

      <Txt size={17} weight={600} style={{ marginTop: 8 }}>
        Why it fits you
      </Txt>
      {opp.fit.map((f) => (
        <View key={f.k + f.t} style={styles.fit}>
          <Pill label={f.k} bg={colors.pink} fontSize={11.5} upper />
          <Txt size={14} lh={1.5} style={{ flex: 1 }}>
            {f.t}
          </Txt>
        </View>
      ))}

      <PrimaryButton
        label="Open in Studio"
        height={58}
        onPress={() => void openInStudio(opp.id, opp.name)}
        style={{ marginTop: 8 }}
      />
      {next ? (
        <Press
          onPress={() => setOpp(next.id)}
          accessibilityLabel={`Next: ${next.name}`}
          style={styles.next}
        >
          <Txt size={14} weight={600}>
            Next: {next.name}
          </Txt>
          <Icon name="chevronRight" size={16} color={colors.blue} strokeWidth={2} />
        </Press>
      ) : null}
      <SkipLink
        label="Not for me"
        onPress={() =>
          dismiss.mutate(opp.id, {
            onSuccess: () => {
              showToast('Hidden. Curo won’t suggest it again.');
              if (next) setOpp(next.id);
              else goHomeRoot();
            },
          })
        }
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { paddingTop: 26, paddingHorizontal: 20, paddingBottom: 28, gap: 14 },
  signals: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, justifyContent: 'center' },
  signal: {
    height: 30,
    paddingHorizontal: 14,
    borderRadius: 15,
    backgroundColor: colors.gray,
    justifyContent: 'center',
  },
  dark: {
    backgroundColor: colors.ink,
    borderRadius: 26,
    padding: 18,
    flexDirection: 'row',
    gap: 14,
    marginTop: 4,
  },
  darkRight: {
    flex: 1,
    borderLeftWidth: 1,
    borderLeftColor: 'rgba(255,255,255,0.18)',
    paddingLeft: 14,
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 2,
    borderColor: colors.ink,
    marginRight: -9,
    alignItems: 'center',
    justifyContent: 'center',
  },
  fit: {
    flexDirection: 'row',
    gap: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.gray,
    borderRadius: 20,
    paddingVertical: 12,
    paddingHorizontal: 14,
  },
  next: {
    alignSelf: 'center',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
});
