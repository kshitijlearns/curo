import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';

import { MatchCard } from './MatchCard';
import { ReelCarousel } from './ReelCarousel';
import { useOpportunities, useReels, useRefreshReels } from '@/api/hooks';
import { Appear, Skeleton } from '@/components/motion';
import { Txt } from '@/components/Txt';
import { DarkButton, Pill, PrimaryButton } from '@/components/ui';
import { TAG_STYLE } from '@/mock/data';
import { useSheetScroll } from '@/screens/shell/useSheetScroll';
import { useApp } from '@/state/app';
import { colors } from '@/theme';

const CARD_W = 284;
const CARD_GAP = 12;

/** Home: previous content carousel with public metrics, then the top-5 opportunity areas. */
export function HomeView() {
  const ref = useSheetScroll();
  const reelsQ = useReels(10);
  const refresh = useRefreshReels();
  const reels = reelsQ.data ?? [];
  const oppsQ = useOpportunities();
  const opps = oppsQ.data ?? [];
  const reelIdx = Math.min(
    useApp((s) => s.reelIdx),
    Math.max(reels.length - 1, 0),
  );
  const openInsights = useApp((s) => s.openInsights);
  const openOpp = useApp((s) => s.openOpp);

  return (
    <ScrollView
      ref={ref}
      contentContainerStyle={{ flexGrow: 1 }}
      showsVerticalScrollIndicator={false}
      refreshControl={
        <RefreshControl
          refreshing={refresh.isPending}
          onRefresh={() => {
            refresh.mutate();
            if (oppsQ.isError) oppsQ.refetch();
          }}
          tintColor={colors.blue}
          colors={[colors.blue]}
        />
      }
    >
      <Appear kind="fade" style={{ flexGrow: 1 }}>
        <View style={styles.top}>
          <MatchCard />
          <View style={styles.titleRow}>
            <Txt size={20} weight={600}>
              Previous content
            </Txt>
            {reels.length ? (
              <Txt size={13} color={colors.muted}>
                {reelIdx + 1} of {reels.length}
              </Txt>
            ) : null}
          </View>
          {reelsQ.isPending ? (
            <Skeleton style={{ height: 286, borderRadius: 22, marginTop: 14 }} />
          ) : reelsQ.isError ? (
            <Txt size={14} lh={1.55} color={colors.muted} style={{ marginTop: 14 }}>
              Couldn’t load your reels: {reelsQ.error.message}. Pull down to try again.
            </Txt>
          ) : reels.length === 0 ? (
            <Txt size={14} lh={1.55} color={colors.muted} style={{ marginTop: 14 }}>
              No public reels yet. Post your first reel and Curo starts tracking it from its first
              hours.
            </Txt>
          ) : (
            <>
              <ReelCarousel reels={reels} heightRatio={270 / 172} onInsights={false} />
              <PrimaryButton
                label="View insights"
                onPress={() => openInsights(reelIdx)}
                style={{ marginTop: 18 }}
              />
            </>
          )}
        </View>

        <View style={styles.opps}>
          <View style={styles.oppsHead}>
            <Txt size={21} weight={600}>
              Opportunity areas
            </Txt>
            {opps.length ? <Pill label={`${opps.length} for you`} bg={colors.white} /> : null}
          </View>
          {oppsQ.isPending ? (
            <View style={{ paddingHorizontal: 20, paddingTop: 16 }}>
              <Skeleton style={{ height: 210, width: CARD_W, borderRadius: 26 }} />
            </View>
          ) : oppsQ.isError ? (
            <Txt size={14} lh={1.55} style={{ paddingHorizontal: 20, paddingTop: 12 }}>
              Couldn’t load your opportunity areas: {oppsQ.error.message}. Pull down to try again.
            </Txt>
          ) : opps.length === 0 ? (
            <Txt size={14} lh={1.55} style={{ paddingHorizontal: 20, paddingTop: 12 }}>
              Curo builds your opportunity areas overnight from your reels, your comments and the
              creators you track. Check back tomorrow.
            </Txt>
          ) : (
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              snapToInterval={CARD_W + CARD_GAP}
              decelerationRate="fast"
              contentContainerStyle={{
                paddingHorizontal: 20,
                paddingTop: 16,
                paddingBottom: 4,
                gap: CARD_GAP,
              }}
            >
              {opps.map((o) => (
                <View key={o.id} style={styles.card}>
                  <View style={styles.cardHead}>
                    <Pill label={o.tag} bg={TAG_STYLE[o.tag].bg} fg={TAG_STYLE[o.tag].fg} />
                    <Txt size={13} color={colors.muted}>
                      <Txt size={17} weight={600}>
                        {o.score_shown}
                      </Txt>
                      /10
                    </Txt>
                  </View>
                  <Txt size={15.5} lh={1.5} style={{ minHeight: 92 }}>
                    {o.card}
                  </Txt>
                  <DarkButton label="Explore more" onPress={() => openOpp(o.id)} />
                </View>
              ))}
            </ScrollView>
          )}
        </View>
      </Appear>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  top: { paddingHorizontal: 20, paddingTop: 24, paddingBottom: 28 },
  titleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' },
  opps: {
    marginTop: 'auto',
    borderTopLeftRadius: 32,
    borderTopRightRadius: 32,
    paddingVertical: 26,
    backgroundColor: colors.lavender,
  },
  oppsHead: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  card: {
    width: CARD_W,
    backgroundColor: colors.white,
    borderRadius: 26,
    padding: 18,
    gap: 12,
    alignItems: 'flex-start',
  },
  cardHead: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    alignSelf: 'stretch',
  },
});
