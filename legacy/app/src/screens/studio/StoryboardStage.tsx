import { useEffect, useRef } from 'react';
import { ScrollView, StyleSheet, useWindowDimensions, View } from 'react-native';

import { useStudio } from './derived';
import { Appear, Press, Skeleton } from '@/components/motion';
import { Sketch, type SketchKind } from '@/components/Sketch';
import { Eyebrow, Txt } from '@/components/Txt';
import { CuroBubble, Dots, PrimaryButton, SkipLink, UserBubble } from '@/components/ui';
import { useApp } from '@/state/app';
import { colors } from '@/theme';

const FRAME_W = 236;
const FRAME_H = 316;
const GAP = 14;
const STEP = FRAME_W + GAP;

/** Step 3: one frame per script beat, filmable with the creator's own setups (logic doc §11). */
export function StoryboardStage() {
  const { width } = useWindowDimensions();
  const { st, project, frames } = useStudio();
  const goFrame = useApp((s) => s.goFrame);
  const toCaption = useApp((s) => s.toCaption);
  const skipToFinal = useApp((s) => s.skipToFinal);
  const scroller = useRef<ScrollView>(null);
  const fi = Math.min(st.frame, Math.max(frames.length - 1, 0));
  const shown = useRef(fi);
  const cur = frames[fi];
  const board = project?.storyboard ?? null;
  const loading = st.busy === 'storyboard';
  const side = (width - FRAME_W) / 2;

  useEffect(() => {
    if (shown.current === fi) return;
    shown.current = fi;
    scroller.current?.scrollTo({ x: fi * STEP, animated: true });
  }, [fi]);

  const onSettle = (x: number) => {
    const i = Math.max(0, Math.min(frames.length - 1, Math.round(x / STEP)));
    if (i !== useApp.getState().studio.frame) {
      shown.current = i;
      goFrame(i);
    }
  };

  if (!board || !frames.length) {
    return (
      <Appear>
        <View style={styles.loadingRow}>
          <Skeleton style={{ width: 200, height: 290, borderRadius: 22, opacity: 0.6 }} />
          <Skeleton style={{ width: 236, height: 316, borderRadius: 22 }} />
          <Skeleton style={{ width: 200, height: 290, borderRadius: 22, opacity: 0.6 }} />
        </View>
        <Txt size={13} color={colors.muted} align="center" style={{ marginTop: 14 }}>
          {loading || st.busy
            ? 'Turning each script line into a shot you can film…'
            : 'Write the script first, then each line becomes a shot.'}
        </Txt>
      </Appear>
    );
  }

  return (
    <Appear>
      <ScrollView
        ref={scroller}
        horizontal
        showsHorizontalScrollIndicator={false}
        snapToInterval={STEP}
        decelerationRate="fast"
        disableIntervalMomentum
        contentOffset={{ x: fi * STEP, y: 0 }}
        onMomentumScrollEnd={(e) => onSettle(e.nativeEvent.contentOffset.x)}
        onScrollEndDrag={(e) => onSettle(e.nativeEvent.contentOffset.x)}
        style={{ marginHorizontal: -20 }}
        contentContainerStyle={{ paddingHorizontal: side, paddingVertical: 8, gap: GAP }}
      >
        {frames.map((f, i) => {
          const on = i === fi;
          const updating = loading && (st.busyFrame === i || !!f.stale);
          return (
            <Press
              key={f.id}
              onPress={() => goFrame(i)}
              accessibilityLabel={`Storyboard frame ${i + 1}`}
              transform={[{ translateY: on ? -4 : 0 }, { scale: on ? 1 : 0.9 }]}
              style={[
                styles.frame,
                { borderColor: on ? colors.blue : colors.gray, opacity: on ? 1 : 0.55 },
              ]}
            >
              <Sketch kind={f.icon_key as SketchKind} />
              <View style={styles.frameLabel}>
                <Txt size={12} weight={600} color={colors.white}>
                  {i + 1} / {frames.length}
                </Txt>
              </View>
              {updating ? (
                <Skeleton
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    opacity: 0.85,
                  }}
                />
              ) : null}
            </Press>
          );
        })}
      </ScrollView>
      <View style={{ marginTop: 4 }}>
        <Dots
          count={frames.length}
          index={fi}
          onGo={goFrame}
          activeWidth={22}
          hit={22}
          label={(n) => `Go to frame ${n}`}
        />
      </View>
      <View style={{ alignItems: 'center', marginTop: 6 }}>
        <Appear kind="pop" key={cur?.t} style={styles.time}>
          <Txt size={14} weight={600} tabular>
            {cur?.t}
          </Txt>
        </Appear>
      </View>

      <Appear kind="fade" key={`script-${fi}-${cur?.line}`} style={styles.scriptCard}>
        <Eyebrow>Script</Eyebrow>
        <Txt size={16} lh={1.55} weight={600}>
          “{cur?.line}”
        </Txt>
      </Appear>

      <View style={styles.details}>
        <Row k="How to record" v={cur?.instruction ?? ''} />
        <Row k="Shot" v={cur?.shot_type ?? ''} />
        <Row k="Text on screen" v={cur?.onscreen_text || '—'} />
        <Row k="Transition" v={cur?.transition || 'Straight cut'} />
        <Row k="Effort" v={`${board.feasibility.label} · ${board.feasibility.detail}`} last />
      </View>

      {loading && st.sent ? (
        <Appear style={{ gap: 8, marginTop: 14 }}>
          <UserBubble text={st.sent} />
          <CuroBubble text="Working on it…" />
        </Appear>
      ) : board.reply ? (
        <Appear style={{ gap: 8, marginTop: 14 }} key={`board-${board.version}`}>
          {board.instruction ? <UserBubble text={board.instruction} /> : null}
          <CuroBubble text={board.reply} />
        </Appear>
      ) : null}

      <PrimaryButton
        label="Proceed to caption & hashtags"
        fontSize={16.5}
        onPress={toCaption}
        disabled={!!st.busy}
        style={{ marginTop: 18, paddingLeft: 22 }}
      />
      <SkipLink label="Skip to final draft" onPress={skipToFinal} style={{ paddingVertical: 6 }} />
    </Appear>
  );
}

function Row({ k, v, last }: { k: string; v: string; last?: boolean }) {
  return (
    <View style={[styles.row, !last && styles.rowLine]}>
      <Txt size={13} color={colors.muted} style={{ width: 104 }}>
        {k}
      </Txt>
      <Txt size={14} weight={600} lh={1.4} style={{ flex: 1 }}>
        {v}
      </Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  loadingRow: {
    flexDirection: 'row',
    gap: 14,
    justifyContent: 'center',
    marginHorizontal: -20,
    overflow: 'hidden',
  },
  frame: {
    width: FRAME_W,
    height: FRAME_H,
    borderWidth: 1.5,
    borderRadius: 24,
    overflow: 'hidden',
    backgroundColor: colors.white,
  },
  frameLabel: {
    position: 'absolute',
    top: 10,
    left: 10,
    height: 26,
    paddingHorizontal: 10,
    borderRadius: 13,
    backgroundColor: colors.ink,
    justifyContent: 'center',
  },
  time: {
    height: 32,
    paddingHorizontal: 14,
    borderRadius: 16,
    backgroundColor: colors.lavender,
    justifyContent: 'center',
  },
  scriptCard: {
    marginTop: 14,
    backgroundColor: colors.pink,
    borderRadius: 20,
    paddingVertical: 14,
    paddingHorizontal: 16,
    gap: 4,
  },
  details: {
    marginTop: 12,
    backgroundColor: colors.gray,
    borderRadius: 22,
    paddingVertical: 4,
    paddingHorizontal: 18,
  },
  row: { flexDirection: 'row', gap: 10, paddingVertical: 12 },
  rowLine: { borderBottomWidth: 1, borderBottomColor: colors.white },
});
