import { StyleSheet, Text, View } from 'react-native';

import { useStudio } from './derived';
import { Icon } from '@/components/Icon';
import { Appear, Skeleton, Spin } from '@/components/motion';
import { Eyebrow, Txt } from '@/components/Txt';
import {
  CenterButton,
  CuroBubble,
  OutlinePill,
  Pill,
  PrimaryButton,
  SkipLink,
  UserBubble,
} from '@/components/ui';
import { NOTE_BG } from '@/lib/studioText';
import { useApp } from '@/state/app';
import { colors, font } from '@/theme';

/** Step 2 before a script exists: the chosen idea and "Generate Script". */
export function IdeaStage() {
  const { st, idea, oppLabel } = useStudio();
  const generateScript = useApp((s) => s.generateScript);
  const skipToFinal = useApp((s) => s.skipToFinal);
  if (!idea) return null;
  return (
    <Appear style={{ gap: 14 }}>
      <View style={styles.ideaCard}>
        <Pill label={oppLabel} bg={colors.pink} fontSize={11.5} upper />
        <Txt size={22} weight={600} lh={1.3} ls={-0.01}>
          {idea.text}
        </Txt>
        {idea.description ? (
          <Txt size={15} lh={1.6} color={colors.muted}>
            {idea.description}
          </Txt>
        ) : null}
        <CenterButton
          label="Generate Script"
          icon="sparkle"
          height={54}
          disabled={!!st.busy}
          onPress={() => generateScript(null)}
          style={{ marginTop: 6 }}
        />
      </View>
      <SkipLink label="Skip to final draft" onPress={skipToFinal} />
    </Appear>
  );
}

/** Step 2: the script, with notes backed by the creator's pattern cards (logic doc §10). */
export function ScriptStage() {
  const { st, project, idea, oppLabel, beats } = useStudio();
  const regenerate = useApp((s) => s.regenerate);
  const toggleNote = useApp((s) => s.toggleNote);
  const toStoryboard = useApp((s) => s.toStoryboard);
  const skipToFinal = useApp((s) => s.skipToFinal);
  const script = project?.script ?? null;
  const loading = st.busy === 'script';
  const firstWrite = loading && !script;

  return (
    <Appear style={{ gap: 14 }}>
      <View style={styles.context}>
        <Eyebrow color={colors.muted}>{oppLabel}</Eyebrow>
        <Txt size={16} weight={600} lh={1.35}>
          {idea?.text}
        </Txt>
      </View>

      {loading && st.sent ? (
        <Appear style={{ gap: 8 }}>
          <UserBubble text={st.sent} />
          <CuroBubble text="Working on it…" />
        </Appear>
      ) : script?.reply ? (
        <Appear style={{ gap: 8 }} key={`reply-${script.version}`}>
          {script.instruction ? <UserBubble text={script.instruction} /> : null}
          <CuroBubble text={script.reply} />
        </Appear>
      ) : null}

      <View style={styles.head}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Txt size={19} weight={600}>
            Your script
          </Txt>
          <Appear kind="pop" key={script?.version ?? 0} style={styles.version}>
            <Txt size={12} weight={600}>
              v{script?.version ?? 1}
            </Txt>
          </Appear>
        </View>
        <OutlinePill
          label="Regenerate"
          height={36}
          fontSize={13}
          disabled={!!st.busy}
          spinning={loading}
          onPress={regenerate}
          icon={
            <Spin active={loading}>
              <Icon name="refresh" size={14} strokeWidth={2} />
            </Spin>
          }
        />
      </View>

      {firstWrite || (loading && !st.sent) ? (
        <View style={{ gap: 10, paddingVertical: 4 }}>
          {[92, 70, 80, 88, 60].map((w, i) => (
            <Skeleton
              key={i}
              delay={i * 100}
              style={{ height: i === 2 ? 14 : 16, borderRadius: 8, width: `${w}%` }}
            />
          ))}
          <Txt size={13} color={colors.muted} style={{ marginTop: 6 }}>
            Writing in your voice, from your strongest reels…
          </Txt>
        </View>
      ) : (
        <View style={{ gap: 16, opacity: loading ? 0.55 : 1 }}>
          {beats.map((b, i) => {
            const note = b.note ?? null;
            const open = st.openNote === b.id;
            const changed =
              (script?.changed_beat_ids ?? []).includes(b.id) && (script?.version ?? 1) > 1;
            return (
              <Appear key={`${script?.version}-${b.id}`} delay={i * 70}>
                {changed ? (
                  <Txt size={11.5} weight={600} color={colors.blue}>
                    Changed
                  </Txt>
                ) : null}
                <Txt size={18} lh={1.6} weight={i === 0 ? 600 : 400}>
                  {b.text}
                </Txt>
                {note ? (
                  <Txt size={14} lh={1.85} style={{ marginTop: 6 }}>
                    <Text style={{ backgroundColor: NOTE_BG[note.type] }}>
                      {' '}
                      <Text style={font(600)}>{note.title}</Text> — {note.desc}{' '}
                    </Text>
                    {'  '}
                    <Text
                      onPress={() => toggleNote(b.id)}
                      accessibilityRole="button"
                      accessibilityState={{ expanded: open }}
                      style={[font(600), styles.why]}
                    >
                      {open ? 'Hide' : 'Why?'}
                    </Text>
                  </Txt>
                ) : null}
                {note && open ? (
                  <Appear kind="fade">
                    <Txt size={13.5} lh={1.6} weight={300} italic style={{ marginTop: 6 }}>
                      {note.evidence}
                    </Txt>
                  </Appear>
                ) : null}
              </Appear>
            );
          })}
          {script ? (
            <Txt size={12} lh={1.55} color={colors.muted}>
              {script.band ? `Best length for you: ${script.band}. ` : ''}Highlighted notes show the
              behaviour Curo associates with a line, from your past reels and similar creators.
              They’re signals, not guarantees.
            </Txt>
          ) : null}
        </View>
      )}

      <PrimaryButton
        label="Proceed to visuals"
        onPress={toStoryboard}
        disabled={!!st.busy || !script}
        style={{ marginTop: 4 }}
      />
      <SkipLink label="Skip to final draft" onPress={skipToFinal} style={{ paddingVertical: 6 }} />
    </Appear>
  );
}

const styles = StyleSheet.create({
  ideaCard: {
    borderWidth: 1,
    borderColor: colors.gray,
    borderRadius: 26,
    paddingVertical: 22,
    paddingHorizontal: 20,
    gap: 12,
  },
  context: {
    backgroundColor: colors.gray,
    borderRadius: 22,
    paddingVertical: 14,
    paddingHorizontal: 16,
    gap: 4,
  },
  head: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 4,
  },
  version: {
    backgroundColor: colors.lavender,
    borderRadius: 10,
    paddingVertical: 2,
    paddingHorizontal: 8,
  },
  why: { fontSize: 13, color: colors.blue, textDecorationLine: 'underline' },
});
