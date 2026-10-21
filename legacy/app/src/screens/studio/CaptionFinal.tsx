import { ScrollView, StyleSheet, View } from 'react-native';
import Animated from 'react-native-reanimated';

import { useStudio } from './derived';
import { Icon } from '@/components/Icon';
import { Appear, Press, Skeleton } from '@/components/motion';
import { Sketch, type SketchKind } from '@/components/Sketch';
import { Eyebrow, Txt } from '@/components/Txt';
import { CenterButton, CuroBubble, OutlinePill, PrimaryButton, UserBubble } from '@/components/ui';
import { MAX_HASHTAGS } from '@/lib/studioText';
import { useApp } from '@/state/app';
import { colors, springOn } from '@/theme';

/** Step 4: three captions that each do a different job, and up to five hashtags (logic doc §12). */
export function CaptionStage() {
  const { st, project, idea } = useStudio();
  const pickCaption = useApp((s) => s.pickCaption);
  const toggleTag = useApp((s) => s.toggleTag);
  const toFinal = useApp((s) => s.toFinal);
  const caps = project?.captions ?? null;
  const loading = st.busy === 'caption';
  const picked = caps?.hashtags ?? [];
  const known = new Map((caps?.candidates ?? []).map((c) => [c.tag, c.kind]));
  const tags = [
    ...(caps?.candidates ?? []).map((c) => c.tag),
    ...picked.filter((t) => !known.has(t)),
  ];
  const niche = picked.filter((t) => (known.get(t) ?? 'niche') !== 'broad').length;

  return (
    <Appear style={{ gap: 12 }}>
      <View style={styles.titleCard}>
        <Txt size={14} weight={600} lh={1.45}>
          {idea?.text}
        </Txt>
      </View>
      <Txt size={18} weight={600} style={{ marginTop: 6 }}>
        Captions
      </Txt>
      {!caps ? (
        <View style={{ gap: 10 }}>
          {[0, 120, 240].map((d) => (
            <Skeleton key={d} delay={d} style={{ height: 96, borderRadius: 22 }} />
          ))}
          <Txt size={13} color={colors.muted}>
            {loading
              ? 'Writing three captions in your usual style…'
              : 'Write the script first, then Curo writes captions from it.'}
          </Txt>
        </View>
      ) : (
        caps.options.map((c, i) => {
          const sel = caps.chosen === i;
          return (
            <Appear key={`${caps.version}-${i}`} delay={i * 70}>
              <Press
                onPress={() => pickCaption(i)}
                accessibilityLabel={c.text}
                accessibilityState={{ selected: sel }}
                transform={[{ translateY: sel ? -3 : 0 }]}
                style={[
                  styles.option,
                  {
                    borderColor: sel ? colors.blue : colors.gray,
                    backgroundColor: sel ? colors.pink : colors.white,
                    opacity: loading ? 0.55 : 1,
                  },
                ]}
              >
                <View style={{ flex: 1, gap: 10 }}>
                  <Txt size={15} lh={1.55}>
                    {c.text}
                  </Txt>
                  <View style={[styles.why, { backgroundColor: sel ? colors.white : colors.gray }]}>
                    <Txt size={12} weight={600}>
                      {c.why}
                    </Txt>
                  </View>
                </View>
                <Radio selected={sel} />
              </Press>
            </Appear>
          );
        })
      )}

      {caps ? (
        <>
          <View style={styles.tagsHead}>
            <Txt size={18} weight={600}>
              Hashtags
            </Txt>
            <Txt size={12.5} color={colors.muted}>
              {picked.length} of {MAX_HASHTAGS} picked · {niche} niche, {picked.length - niche}{' '}
              broad
            </Txt>
          </View>
          <View style={styles.tags}>
            {tags.map((t) => {
              const on = picked.includes(t);
              return (
                <Press
                  key={t}
                  onPress={() => toggleTag(t)}
                  accessibilityLabel={`#${t}`}
                  accessibilityState={{ selected: on }}
                  transform={[{ scale: on ? 1.04 : 1 }, { translateX: st.tagNudge === t ? 6 : 0 }]}
                  style={[styles.tag, { backgroundColor: on ? colors.ink : colors.gray }]}
                >
                  <Txt size={13.5} weight={on ? 600 : 400} color={on ? colors.white : colors.ink}>
                    #{t}
                  </Txt>
                  <Txt
                    size={11}
                    weight={on ? 600 : 400}
                    color={on ? colors.white : colors.ink}
                    style={{ opacity: 0.8 }}
                  >
                    {known.get(t) ?? 'yours'}
                  </Txt>
                </Press>
              );
            })}
          </View>
        </>
      ) : null}

      {loading && st.sent ? (
        <Appear style={{ gap: 8, marginTop: 4 }}>
          <UserBubble text={st.sent} />
          <CuroBubble text="Working on it…" />
        </Appear>
      ) : caps?.instruction && caps.reply ? (
        <Appear style={{ gap: 8, marginTop: 4 }} key={`caps-${caps.version}`}>
          <UserBubble text={caps.instruction} />
          <CuroBubble text={caps.reply} />
        </Appear>
      ) : null}

      <PrimaryButton
        label="Continue to final draft"
        onPress={toFinal}
        disabled={!!st.busy}
        style={{ marginTop: 8 }}
      />
    </Appear>
  );
}

/** Step 5: everything for this reel in one place, under one project. No "Simulate" here (logic doc §12). */
export function FinalStage() {
  const { st, project, idea, oppLabel, beats, frames } = useStudio();
  const editScript = useApp((s) => s.editScript);
  const toStoryboard = useApp((s) => s.toStoryboard);
  const goFrame = useApp((s) => s.goFrame);
  const goStep = useApp((s) => s.goStep);
  const saveDraft = useApp((s) => s.saveDraft);
  const caps = project?.captions ?? null;
  const caption = caps && caps.chosen != null ? (caps.options[caps.chosen]?.text ?? '') : '';
  const length = beats.length ? beats[beats.length - 1].t.split('– ')[1] : 'not started';
  const saved = project?.status === 'saved';

  return (
    <Appear style={{ gap: 12 }}>
      <View style={styles.pinkCard}>
        <Eyebrow>{oppLabel}</Eyebrow>
        <Txt size={20} weight={600} lh={1.3}>
          {idea?.text}
        </Txt>
      </View>

      <View style={styles.box}>
        <View style={styles.boxHead}>
          <Eyebrow>Script · {length}</Eyebrow>
          <OutlinePill label={beats.length ? 'Edit' : 'Generate'} onPress={editScript} />
        </View>
        {!beats.length ? (
          <Txt size={14} color={colors.muted}>
            No script yet — you skipped this step.
          </Txt>
        ) : null}
        {beats.map((b) => (
          <View key={b.id} style={{ flexDirection: 'row', gap: 8 }}>
            <Txt size={12} color={colors.muted} tabular style={{ width: 76, paddingTop: 2 }}>
              {b.t}
            </Txt>
            <Txt size={14} lh={1.5} style={{ flex: 1 }}>
              {b.text}
            </Txt>
          </View>
        ))}
      </View>

      <View style={[styles.box, { gap: 10 }]}>
        <View style={styles.boxHead}>
          <Eyebrow>
            Storyboard · {frames.length ? `${frames.length} frames` : 'not started'}
          </Eyebrow>
          {beats.length ? <OutlinePill label="Edit" onPress={() => void toStoryboard()} /> : null}
        </View>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={{ marginHorizontal: -18 }}
          contentContainerStyle={{ paddingHorizontal: 18, gap: 8 }}
        >
          {frames.map((f, i) => (
            <Press
              key={f.id}
              onPress={() => void toStoryboard().then(() => goFrame(i))}
              accessibilityLabel={`Open frame ${i + 1}`}
              style={{ width: 82, gap: 5 }}
            >
              <View style={styles.mini}>
                <Sketch kind={f.icon_key as SketchKind} />
              </View>
              <Txt size={11} color={colors.muted} tabular>
                {f.t}
              </Txt>
            </Press>
          ))}
        </ScrollView>
      </View>

      <View style={styles.box}>
        <View style={styles.boxHead}>
          <Eyebrow>Caption</Eyebrow>
          {beats.length ? <OutlinePill label="Edit" onPress={() => goStep(3)} /> : null}
        </View>
        <Txt size={15} lh={1.55} color={caption ? colors.ink : colors.muted}>
          {caption || 'No caption yet.'}
        </Txt>
        {caps?.hashtags.length ? (
          <Txt size={13.5} lh={1.6} weight={600}>
            {caps.hashtags.map((t) => `#${t}`).join(' ')}
          </Txt>
        ) : null}
      </View>

      <CenterButton
        label={saved ? 'Saved — save again' : 'Save draft'}
        fontSize={15.5}
        disabled={!!st.busy}
        onPress={saveDraft}
      />
    </Appear>
  );
}

function Radio({ selected }: { selected: boolean }) {
  return (
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
  );
}

const styles = StyleSheet.create({
  titleCard: {
    backgroundColor: colors.gray,
    borderRadius: 20,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  option: {
    borderWidth: 1.5,
    borderRadius: 22,
    padding: 16,
    flexDirection: 'row',
    gap: 12,
    alignItems: 'flex-start',
  },
  why: { alignSelf: 'flex-start', borderRadius: 11, paddingVertical: 4, paddingHorizontal: 10 },
  radio: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tagsHead: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    marginTop: 8,
  },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tag: {
    height: 38,
    paddingHorizontal: 14,
    borderRadius: 19,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  pinkCard: { backgroundColor: colors.pink, borderRadius: 26, padding: 18, gap: 6 },
  box: {
    borderWidth: 1,
    borderColor: colors.gray,
    borderRadius: 26,
    paddingVertical: 16,
    paddingHorizontal: 18,
    gap: 8,
  },
  boxHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  mini: {
    width: 82,
    height: 110,
    borderWidth: 1,
    borderColor: colors.gray,
    borderRadius: 14,
    overflow: 'hidden',
    backgroundColor: colors.white,
  },
});
