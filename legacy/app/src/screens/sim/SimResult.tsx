import { StyleSheet, View } from 'react-native';
import Animated from 'react-native-reanimated';

import { LoadingRing, SampleTakes } from './SimIntro';
import { useSimulation } from '@/api/hooks';
import type { SimEdit, SimItem, Simulation } from '@/api/simulator';
import { Icon } from '@/components/Icon';
import { AskCuroThread } from '@/components/AskCuroThread';
import { Appear, Press } from '@/components/motion';
import { ReelThumb } from '@/components/ReelThumb';
import { ScoreRing } from '@/components/ScoreRing';
import { Txt } from '@/components/Txt';
import { CenterButton, ChoiceChips, CuroMark, OutlinePill } from '@/components/ui';
import { pickVideo } from '@/lib/pickVideo';
import { AUDIENCES, reportRow, scoreDelta, SIM_STEPS, type DnaTab } from '@/lib/simText';
import { useApp } from '@/state/app';
import { colors, EASE, springOn } from '@/theme';

type Evidence = SimItem['evidence'][number];

/** The draft's title when it's linked, else the upload's name. */
function useDraftTitle(sim?: Simulation) {
  const upload = useApp((s) => s.sim.upload);
  const idea = useApp((s) => s.studio.ideaTitle);
  return sim?.project_title ?? (sim ? upload?.name : idea) ?? upload?.name ?? 'Your reel';
}

/** "Simulating…" with the five reading steps ticking off as the job reports them. */
export function SimLoading() {
  const step = useApp((s) => s.sim.step);
  const linked = useApp((s) => s.sim.linked && !!s.studio.ideaTitle);
  const idea = useApp((s) => s.studio.ideaTitle);
  const upload = useApp((s) => s.sim.upload);
  const title = (linked ? idea : upload?.name) ?? 'your reel';
  const short = title.length > 36 ? `${title.slice(0, 34)}…` : title;
  return (
    <Appear kind="fade" style={styles.loading}>
      <View style={{ width: 84, height: 84, alignItems: 'center', justifyContent: 'center' }}>
        <View style={{ position: 'absolute' }}>
          <LoadingRing size={84} track={colors.gray} />
        </View>
        <View style={styles.loadingMark}>
          <Icon name="sparkle" size={16} color={colors.blue} />
        </View>
      </View>
      <Txt size={17} weight={600} align="center">
        Simulating “{short}”
      </Txt>
      <View style={styles.steps}>
        {SIM_STEPS.map((label, k) => {
          const done = step > k;
          const cur = step === k;
          return (
            <View key={label} style={styles.stepRow}>
              <Animated.View
                style={[
                  styles.stepDot,
                  {
                    borderColor: done || cur ? colors.blue : colors.lavender,
                    backgroundColor: done ? colors.blue : colors.white,
                    transform: [{ scale: cur ? 1.15 : 1 }],
                  },
                  springOn('backgroundColor', 'borderColor', 'transform'),
                ]}
              >
                {done ? (
                  <Appear kind="pop">
                    <Icon name="check" size={12} strokeWidth={3} color={colors.white} />
                  </Appear>
                ) : null}
              </Animated.View>
              <Txt
                size={14.5}
                weight={cur ? 600 : 400}
                color={done || cur ? colors.ink : colors.muted}
              >
                {label}
              </Txt>
            </View>
          );
        })}
      </View>
    </Appear>
  );
}

/** The full estimate (logic doc §13), for the audience on screen. */
export function SimResult() {
  const state = useApp();
  const { sim: ui } = state;
  const { data: sim } = useSimulation(ui.simulationId);
  const title = useDraftTitle(sim);
  const threadKey = ui.simulationId ? `sim:${ui.simulationId}` : null;
  const thread = useApp((s) => (threadKey ? s.chat[threadKey] : undefined));
  if (!sim?.result) {
    return (
      <View style={styles.loading}>
        <LoadingRing size={40} track={colors.gray} />
      </View>
    );
  }
  const result = sim.result;
  const audience = result.audiences[ui.audience];
  const score = audience.score;
  const delta = scoreDelta(sim, ui.audience);
  const allEdits = sim.edits ?? [];
  const edits = new Map(allEdits.map((e) => [e.id, e]));
  const shown = audience.edit_ids.map((id) => edits.get(id)).filter((e): e is SimEdit => !!e);
  const applied = allEdits.filter((e) => e.applied);
  const addressed = (feature: string) => applied.some((e) => feature in e.feature_change);
  const pending = shown.filter((e) => ui.pending[e.id] && !e.applied).length;
  const allApplied = shown.length > 0 && shown.every((e) => e.applied);
  const linked = result.linked && !!sim.project_id;

  return (
    <Appear>
      <View style={styles.top}>
        <Press onPress={state.backToIntro} accessibilityLabel="Back to upload" style={styles.back}>
          <Icon name="back" size={18} strokeWidth={1.8} />
        </Press>
        <View style={{ flex: 1 }}>
          <Txt size={11.5} weight={600} ls={0.1} upper color={colors.muted}>
            Simulation
          </Txt>
          <Txt size={15} weight={600} numberOfLines={1}>
            {title}
          </Txt>
        </View>
      </View>

      <View style={{ alignItems: 'center', marginTop: 18, paddingHorizontal: 20 }}>
        <Appear kind="pop" style={styles.scoreWrap}>
          <ScoreRing progress={score / 100} size={148} duration={1200} delay={150}>
            <Txt size={56} weight={300} ls={-0.045} style={{ lineHeight: 60 }}>
              {score}
            </Txt>
            <Txt size={12.5} color={colors.muted}>
              out of 100
            </Txt>
          </ScoreRing>
        </Appear>
        <Txt size={19} weight={600} align="center" style={{ marginTop: 16 }}>
          {audience.label}
        </Txt>
        {delta != null && delta !== 0 ? (
          <Appear kind="rise" style={[styles.delta, delta < 0 && { backgroundColor: colors.pink }]}>
            <Icon name="arrowUpRight" size={12} strokeWidth={2.6} />
            <Txt size={13} weight={600}>
              {delta > 0 ? '+' : '−'}
              {Math.abs(delta)} since last run
            </Txt>
          </Appear>
        ) : null}
        <Txt size={14.5} lh={1.6} align="center" color={colors.muted} style={{ marginTop: 8 }}>
          {audience.summary}
        </Txt>
        <Txt size={12.5} align="center" color={colors.muted} style={{ marginTop: 6 }}>
          Likely to do better than {score}% of your recent reels
        </Txt>
        <View style={{ marginTop: 14 }}>
          <ChoiceChips
            options={AUDIENCES}
            value={ui.audience}
            onChange={state.setAudience}
            height={36}
            fontSize={13}
            gap={6}
            center
          />
        </View>
      </View>

      <View style={styles.body}>
        <View style={styles.report}>
          <View style={styles.reportHead}>
            <View>
              <Txt size={17} weight={600} color={colors.white}>
                Predicted report
              </Txt>
              <Txt size={12} color={colors.gray}>
                Estimate based on your history
              </Txt>
            </View>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <View
                style={{ width: 2, height: 14, borderRadius: 1, backgroundColor: colors.white }}
              />
              <Txt size={12} color={colors.gray}>
                your baseline
              </Txt>
            </View>
          </View>
          {result.report.map((row) => {
            const r = reportRow(row);
            if (!r) {
              return (
                <View key={row.metric} style={styles.mRow}>
                  <Txt size={14} color={colors.white}>
                    {row.label[0].toUpperCase() + row.label.slice(1)}
                  </Txt>
                  <Txt size={12} color={colors.gray}>
                    Not enough of your history to estimate this yet
                  </Txt>
                </View>
              );
            }
            return (
              <View key={row.metric} style={styles.mRow}>
                <View style={styles.mHead}>
                  <Txt size={14} color={colors.white}>
                    {r.name}
                  </Txt>
                  <Txt size={15} weight={600} color={colors.white} tabular>
                    {r.value}
                  </Txt>
                </View>
                <View style={styles.bar}>
                  <Animated.View
                    style={{
                      position: 'absolute',
                      left: 0,
                      top: 0,
                      bottom: 0,
                      borderRadius: 4,
                      width: `${Math.min(100, (r.pred / r.max) * 100)}%`,
                      backgroundColor: r.above ? colors.blue : colors.pink,
                      transitionProperty: 'width',
                      transitionDuration: 700,
                      transitionTimingFunction: EASE.bars,
                    }}
                  />
                  <View style={[styles.tick, { left: `${(r.baseline / r.max) * 100}%` }]} />
                </View>
                <Txt size={12} color={r.above ? colors.lavender : colors.pink}>
                  {r.change} vs your baseline ({r.base}){r.above ? '' : ' · below'}
                </Txt>
              </View>
            );
          })}
          <View style={styles.best}>
            <View style={styles.bestIcon}>
              <Icon name="clock" size={18} strokeWidth={1.8} color={colors.white} />
            </View>
            <View style={{ flex: 1, gap: 3 }}>
              <Txt size={14.5} weight={600} color={colors.white}>
                {result.best_time
                  ? `Best time to post: ${result.best_time.label}`
                  : 'Best time to post: not enough history yet'}
              </Txt>
              <Txt size={13} lh={1.55} weight={300} color={colors.gray}>
                {result.best_time
                  ? result.best_time.fact
                  : 'Curo needs at least two of your reels posted at the same day and time to suggest a slot.'}
              </Txt>
            </View>
          </View>
        </View>
        <Txt size={12.5} lh={1.5} color={colors.muted} style={{ marginHorizontal: 2 }}>
          {result.accuracy}
        </Txt>
        {result.notes.map((n) => (
          <Txt key={n} size={12.5} lh={1.5} color={colors.muted} style={{ marginHorizontal: 2 }}>
            {n}
          </Txt>
        ))}

        <H2>What’s working</H2>
        {audience.working.length === 0 ? (
          <Empty text="Nothing in this recording is clearly linked with more in your patterns yet." />
        ) : null}
        {audience.working.map((w) => {
          const key = `w:${w.key}`;
          const open = !!ui.openEv[key];
          return (
            <View key={w.key} style={styles.cardBorder}>
              <View style={styles.cardRow}>
                <View style={[styles.mark, { backgroundColor: colors.lavender }]}>
                  <Icon name="check" size={14} strokeWidth={2.8} color={colors.blue} />
                </View>
                <Txt size={15} lh={1.55} style={{ flex: 1 }}>
                  {w.text}
                </Txt>
              </View>
              <EvidenceButton open={open} onPress={() => state.toggleSimEv(key)} />
              {open ? <EvidenceList items={w.evidence} /> : null}
            </View>
          );
        })}

        <H2>What’s holding it back</H2>
        {audience.holding.length === 0 ? (
          <Empty text="Nothing in this recording is linked with less in your patterns." />
        ) : null}
        {audience.holding.map((h) => {
          const res = addressed(h.feature);
          const key = `h:${h.key}`;
          const open = !!ui.openEv[key];
          return (
            <Animated.View
              key={h.key}
              style={[
                styles.cardBorder,
                {
                  borderColor: res ? colors.gray : colors.pink,
                  backgroundColor: res ? colors.gray : colors.white,
                },
                springOn('backgroundColor', 'borderColor'),
              ]}
            >
              <View style={styles.cardRow}>
                <View
                  style={[styles.mark, { backgroundColor: res ? colors.lavender : colors.pink }]}
                >
                  <Txt size={15} weight={600} color={res ? colors.blue : colors.ink}>
                    {res ? '✓' : '!'}
                  </Txt>
                </View>
                <Txt
                  size={15}
                  lh={1.55}
                  color={res ? colors.muted : colors.ink}
                  style={{ flex: 1 }}
                >
                  {h.text}
                </Txt>
              </View>
              <View style={styles.holdActions}>
                <FrameButton
                  label={h.frame_label}
                  onPress={linked && h.frame != null ? () => state.viewFrame(h.frame!) : null}
                />
                <EvidenceButton
                  open={open}
                  onPress={() => state.toggleSimEv(key)}
                  style={{ marginLeft: 0 }}
                />
                {res ? (
                  <Appear kind="pop">
                    <Txt size={12.5} weight={600}>
                      Addressed in your draft
                    </Txt>
                  </Appear>
                ) : null}
              </View>
              {open ? <EvidenceList items={h.evidence} /> : null}
            </Animated.View>
          );
        })}

        <H2>What to change</H2>
        <Txt
          size={13.5}
          lh={1.55}
          color={colors.muted}
          style={{ marginTop: -6, marginHorizontal: 2 }}
        >
          {shown.length
            ? linked
              ? 'Pick the edits to apply. Curo updates your Studio script and storyboard; then re-record and upload the new take.'
              : 'Pick the edits to make. Then re-record and upload the new take.'
            : 'None of the changes Curo tested would raise this estimate.'}
        </Txt>
        {shown.map((ed) => {
          const on = !!ui.pending[ed.id];
          const checked = ed.applied || on;
          const gain = ed.gains[ui.audience];
          return (
            <Press
              key={ed.id}
              onPress={() => !ed.applied && state.toggleEdit(ed.id)}
              disabled={ed.applied}
              accessibilityRole="checkbox"
              accessibilityState={{ checked, disabled: ed.applied }}
              accessibilityLabel={ed.title}
              transform={[{ translateY: on && !ed.applied ? -3 : 0 }]}
              style={[
                styles.edit,
                {
                  borderColor: on && !ed.applied ? colors.blue : colors.gray,
                  backgroundColor: ed.applied ? colors.gray : on ? colors.pink : colors.white,
                },
              ]}
            >
              <Animated.View
                style={[
                  styles.check,
                  {
                    borderColor: checked ? colors.blue : colors.lavender,
                    backgroundColor: checked ? colors.blue : 'rgba(91,115,242,0)',
                    transform: [{ scale: on && !ed.applied ? 1.1 : 1 }],
                  },
                  springOn('backgroundColor', 'borderColor', 'transform'),
                ]}
              >
                {checked ? (
                  <Appear kind="pop">
                    <Icon name="check" size={13} strokeWidth={3} color={colors.white} />
                  </Appear>
                ) : null}
              </Animated.View>
              <View style={{ flex: 1, gap: 5 }}>
                <View style={styles.editHead}>
                  <Txt size={15} weight={600} style={{ flex: 1 }}>
                    {ed.title}
                  </Txt>
                  <View
                    style={[
                      styles.gain,
                      { backgroundColor: ed.applied ? colors.white : colors.lavender },
                    ]}
                  >
                    <Txt size={12} weight={600}>
                      {ed.applied ? 'Applied' : `+${gain} est.`}
                    </Txt>
                  </View>
                </View>
                <Txt size={13.5} lh={1.55} color={colors.muted}>
                  {ed.description}
                </Txt>
                <Txt size={12} weight={600} color={colors.blue}>
                  {[ed.frame_label, ed.effort === 'edit_only' ? 'Edit only' : 'Needs a reshoot']
                    .filter(Boolean)
                    .join(' · ')}
                </Txt>
              </View>
            </Press>
          );
        })}
        {shown.length ? (
          <CenterButton
            label={
              ui.applying
                ? 'Applying…'
                : allApplied
                  ? 'All edits applied'
                  : pending
                    ? `Edit & re-run (${pending})`
                    : 'Select edits to re-run'
            }
            icon="refresh"
            disabled={pending === 0 || ui.applying}
            onPress={() => void state.editRerun()}
          />
        ) : null}
        {ui.awaitingTake || applied.length ? <RerunCard /> : null}

        {result.compare.length ? (
          <View style={styles.compare}>
            <Txt size={17} weight={600}>
              Compared with your Studio draft
            </Txt>
            {result.compare.map((c) => (
              <View key={c.kind + c.text} style={styles.compareRow}>
                <View style={styles.compareDot} />
                <Txt size={13.5} lh={1.5} style={{ flex: 1 }}>
                  {c.text}
                </Txt>
              </View>
            ))}
          </View>
        ) : null}

        <DnaPanel tab={ui.dnaTab} onTab={state.setDnaTab} rows={result.dna[ui.dnaTab]} />

        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 8 }}>
          <CuroMark size={34} />
          <Txt size={20} weight={600}>
            Ask Curo
          </Txt>
        </View>
        {!thread?.length ? (
          <Txt size={13.5} color={colors.muted} style={{ marginTop: -4, marginHorizontal: 2 }}>
            Ask about any part of this simulation below, or try a what-if: “what if I end with a
            send prompt?”
          </Txt>
        ) : null}
        <View style={{ marginTop: -18 }}>
          <AskCuroThread threadKey={threadKey} />
        </View>

        <View style={styles.actions}>
          <ActionButton
            label="Publish"
            bg={colors.blue}
            fg={colors.white}
            onPress={state.publish}
          />
          <ActionButton
            label="Save draft"
            bg={colors.ink}
            fg={colors.white}
            onPress={() => void state.saveDraft()}
          />
          <ActionButton
            label="Discard"
            bg={colors.white}
            fg={colors.ink}
            border
            onPress={state.discard}
          />
        </View>
        <Txt size={12} lh={1.6} color={colors.muted} style={{ marginHorizontal: 2, marginTop: 2 }}>
          Estimates come from your own history and similar public posts. They are not predictions
          from Instagram and can’t account for everything the platform does.
          {linked ? '' : ' Not linked to a Studio draft.'}
        </Txt>
      </View>
    </Appear>
  );
}

/** After the edits: upload the re-recorded take to re-run against this result. */
function RerunCard() {
  const uploading = useApp((s) => s.sim.uploading);
  const rerunPicked = useApp((s) => s.rerunPicked);
  const rerunSample = useApp((s) => s.rerunSample);
  const pick = async () => {
    const video = await pickVideo();
    if (video) await rerunPicked(video);
  };
  return (
    <Appear kind="rise" style={styles.rerun}>
      <Txt size={16} weight={600}>
        Re-record with the edits, then re-run
      </Txt>
      <Txt size={13.5} lh={1.55} color={colors.muted}>
        Curo re-runs on the new take and shows the score next to this one.
      </Txt>
      {uploading ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <LoadingRing size={28} track={colors.white} />
          <Txt size={14} weight={600}>
            Uploading…
          </Txt>
        </View>
      ) : (
        <>
          <OutlinePill label="Upload the new take" height={40} onPress={() => void pick()} />
          <SampleTakes onPick={(n, t) => void rerunSample(n, t)} label="Or use a sample take:" />
        </>
      )}
    </Appear>
  );
}

function H2({ children }: { children: React.ReactNode }) {
  return (
    <Txt size={20} weight={600} style={{ marginTop: 8 }}>
      {children}
    </Txt>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <Txt size={13.5} lh={1.55} color={colors.muted} style={{ marginTop: -6, marginHorizontal: 2 }}>
      {text}
    </Txt>
  );
}

function EvidenceButton({
  open,
  onPress,
  style,
}: {
  open: boolean;
  onPress: () => void;
  style?: object;
}) {
  return (
    <Press
      onPress={onPress}
      accessibilityState={{ expanded: open }}
      accessibilityLabel={open ? 'Hide evidence' : 'See evidence'}
      style={[styles.evBtn, style]}
    >
      <Txt size={12.5} weight={600}>
        {open ? 'Hide evidence' : 'See evidence'}
      </Txt>
      <Animated.View
        style={[{ transform: [{ rotate: open ? '180deg' : '0deg' }] }, springOn('transform')]}
      >
        <Icon name="chevronDown" size={13} strokeWidth={2.2} />
      </Animated.View>
    </Press>
  );
}

/** "Frame 1 · Hook →" opens the linked storyboard; without one, the moment is named only. */
function FrameButton({ label, onPress }: { label?: string | null; onPress: (() => void) | null }) {
  if (!label) return null;
  if (!onPress) {
    return (
      <View style={[styles.frameBtn, { backgroundColor: colors.gray }]}>
        <Txt size={12.5} weight={600}>
          {label}
        </Txt>
      </View>
    );
  }
  return (
    <Press
      onPress={onPress}
      accessibilityLabel={`${label}, open in storyboard`}
      style={styles.frameBtn}
    >
      <Txt size={12.5} weight={600} color={colors.white}>
        {label} →
      </Txt>
    </Press>
  );
}

function EvidenceList({ items }: { items: Evidence[] }) {
  if (!items.length) {
    return (
      <Txt size={12.5} color={colors.muted} style={{ marginLeft: 42 }}>
        No reels to show for this yet.
      </Txt>
    );
  }
  return (
    <Appear kind="fade" style={{ gap: 8, marginLeft: 42 }}>
      {items.map((ev, i) => (
        <Appear kind="rise" key={i} style={styles.ev}>
          <View style={{ width: 42, height: 58, borderRadius: 10, overflow: 'hidden' }}>
            <ReelThumb tone={ev.tone} compact height={58} />
          </View>
          <View style={{ flex: 1, gap: 2 }}>
            <Txt size={12} color={colors.muted}>
              {ev.who}
            </Txt>
            <Txt size={13.5} weight={600} lh={1.3}>
              {ev.title}
            </Txt>
            <Txt size={12.5}>{ev.stat}</Txt>
          </View>
        </Appear>
      ))}
    </Appear>
  );
}

function DnaPanel({
  tab,
  onTab,
  rows,
}: {
  tab: DnaTab;
  onTab: (t: DnaTab) => void;
  rows: string[][];
}) {
  return (
    <View style={styles.dna}>
      <Txt size={17} weight={600}>
        Draft DNA
      </Txt>
      <ChoiceChips
        options={[
          { id: 'content' as const, label: 'Content' },
          { id: 'production' as const, label: 'Production' },
          { id: 'trend' as const, label: 'Trend' },
        ]}
        value={tab}
        onChange={onTab}
        height={36}
        fontSize={13}
        idle={colors.white}
        role="tab"
        gap={6}
      />
      <Appear kind="fade" key={tab}>
        {rows.map(([k, v]) => (
          <View key={k} style={styles.dnaRow}>
            <Txt size={12.5} color={colors.muted} style={{ width: 112 }}>
              {k}
            </Txt>
            <Txt
              size={13.5}
              lh={1.45}
              weight={600}
              color={v === 'Unknown' ? colors.muted : colors.ink}
              style={{ flex: 1 }}
            >
              {v}
            </Txt>
          </View>
        ))}
      </Appear>
    </View>
  );
}

function ActionButton({
  label,
  bg,
  fg,
  border,
  onPress,
}: {
  label: string;
  bg: string;
  fg: string;
  border?: boolean;
  onPress: () => void;
}) {
  return (
    <Press
      onPress={onPress}
      accessibilityLabel={label}
      style={[
        styles.action,
        { backgroundColor: bg },
        border ? { borderWidth: 1.5, borderColor: colors.lavender } : null,
      ]}
    >
      <Txt size={15} weight={600} color={fg}>
        {label}
      </Txt>
    </Press>
  );
}

const styles = StyleSheet.create({
  loading: { alignItems: 'center', gap: 18, paddingVertical: 30, paddingHorizontal: 20 },
  loadingMark: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.lavender,
    alignItems: 'center',
    justifyContent: 'center',
  },
  steps: {
    alignSelf: 'stretch',
    backgroundColor: colors.gray,
    borderRadius: 24,
    paddingVertical: 6,
    paddingHorizontal: 18,
  },
  stepRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 11 },
  stepDot: {
    width: 26,
    height: 26,
    borderRadius: 13,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  top: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingTop: 22,
    paddingHorizontal: 20,
  },
  back: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.gray,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scoreWrap: {
    width: 164,
    height: 164,
    borderRadius: 82,
    backgroundColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
  },
  delta: {
    marginTop: 8,
    height: 30,
    paddingHorizontal: 12,
    borderRadius: 15,
    backgroundColor: colors.lavender,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  body: { paddingTop: 20, paddingHorizontal: 20, paddingBottom: 26, gap: 14 },
  report: {
    backgroundColor: colors.ink,
    borderRadius: 26,
    paddingTop: 18,
    paddingHorizontal: 18,
    paddingBottom: 8,
  },
  reportHead: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  mRow: {
    gap: 8,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.12)',
  },
  mHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 },
  bar: { height: 8, borderRadius: 4, backgroundColor: 'rgba(255,255,255,0.14)' },
  tick: {
    position: 'absolute',
    top: -4,
    bottom: -4,
    width: 2,
    borderRadius: 1,
    backgroundColor: colors.white,
  },
  best: {
    flexDirection: 'row',
    gap: 12,
    alignItems: 'flex-start',
    paddingTop: 14,
    paddingBottom: 12,
  },
  bestIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.blue,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardBorder: { borderWidth: 1, borderColor: colors.gray, borderRadius: 24, padding: 16, gap: 10 },
  cardRow: { flexDirection: 'row', gap: 12, alignItems: 'flex-start' },
  mark: { width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
  evBtn: {
    alignSelf: 'flex-start',
    marginLeft: 42,
    height: 32,
    paddingHorizontal: 12,
    borderRadius: 16,
    backgroundColor: colors.gray,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  holdActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginLeft: 42,
    alignItems: 'center',
  },
  frameBtn: {
    height: 32,
    paddingHorizontal: 12,
    borderRadius: 16,
    backgroundColor: colors.ink,
    justifyContent: 'center',
  },
  ev: {
    flexDirection: 'row',
    gap: 12,
    alignItems: 'center',
    backgroundColor: colors.gray,
    borderRadius: 18,
    padding: 8,
  },
  edit: {
    borderWidth: 1.5,
    borderRadius: 24,
    padding: 16,
    flexDirection: 'row',
    gap: 12,
    alignItems: 'flex-start',
  },
  check: {
    width: 24,
    height: 24,
    borderRadius: 8,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  editHead: { flexDirection: 'row', justifyContent: 'space-between', gap: 8, alignItems: 'center' },
  gain: { borderRadius: 10, paddingVertical: 2, paddingHorizontal: 8 },
  rerun: {
    borderWidth: 1.5,
    borderColor: colors.blue,
    borderStyle: 'dashed',
    borderRadius: 24,
    padding: 16,
    gap: 10,
  },
  compare: { borderWidth: 1, borderColor: colors.gray, borderRadius: 24, padding: 16, gap: 10 },
  compareRow: { flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
  compareDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.pink,
    marginTop: 7,
  },
  dna: { backgroundColor: colors.gray, borderRadius: 26, padding: 16, gap: 12, marginTop: 4 },
  dnaRow: {
    flexDirection: 'row',
    gap: 10,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: colors.white,
  },
  actions: { flexDirection: 'row', gap: 8, marginTop: 10 },
  action: { flex: 1, height: 50, borderRadius: 25, alignItems: 'center', justifyContent: 'center' },
});
