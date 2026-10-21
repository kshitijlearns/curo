import { StyleSheet, View } from 'react-native';

import { Icon } from '@/components/Icon';
import { Appear, TypingDots } from '@/components/motion';
import { Txt } from '@/components/Txt';
import { CenterButton, CuroMark, Pill, UserBubble } from '@/components/ui';
import type { Verdict } from '@/lib/studioText';
import { useApp, type ValidationTurn } from '@/state/app';
import { colors } from '@/theme';

const VERDICT_STYLE: Record<Verdict, { bg: string; fg: string }> = {
  Strong: { bg: colors.blue, fg: colors.white },
  'Worth trying': { bg: colors.lavender, fg: colors.ink },
  Risky: { bg: colors.pink, fg: colors.ink },
};

/**
 * The Studio tab opened from the nav: "Type any idea or thoughts…". Curo scores the idea
 * with the idea formula and replies with a verdict, two reasons and tweaks (logic doc §9).
 */
export function ValidateChat({ minHeight, quiet }: { minHeight: number; quiet?: boolean }) {
  const turns = useApp((s) => s.studio.validations);

  if (!turns.length && quiet) return null; // Ask Curo's answers are on screen instead
  if (!turns.length) {
    return (
      <Appear kind="fade" style={[styles.hero, { minHeight }]}>
        <Appear kind="pop" style={styles.heroMark}>
          <Icon name="sparkle" size={26} color={colors.blue} />
        </Appear>
        <Txt size={20} lh={1.45} weight={300} align="center">
          Type any idea or thoughts you have here to validate them with Curo.
        </Txt>
      </Appear>
    );
  }

  return (
    <View style={styles.thread}>
      {turns.map((turn) => (
        <View key={turn.id} style={{ gap: 10 }}>
          <Appear>
            <UserBubble text={turn.text} />
          </Appear>
          {turn.result ? (
            <ValidationCard turn={turn} />
          ) : turn.error ? (
            <Txt size={14} lh={1.5} color={colors.muted}>
              {turn.error}
            </Txt>
          ) : (
            <TypingDots />
          )}
        </View>
      ))}
    </View>
  );
}

function ValidationCard({ turn }: { turn: ValidationTurn }) {
  const develop = useApp((s) => s.developValidated);
  const busy = useApp((s) => !!s.studio.busy);
  const r = turn.result!;
  const style = VERDICT_STYLE[r.verdict as Verdict];
  return (
    <Appear style={styles.card}>
      <View style={styles.head}>
        <CuroMark />
        <Pill label={r.verdict} bg={style.bg} fg={style.fg} height={28} fontSize={13} />
        <Txt size={12.5} color={colors.muted}>
          Idea score {r.score.toFixed(2)}
        </Txt>
      </View>
      {r.reasons.map((reason) => (
        <View key={reason.text} style={{ gap: 6 }}>
          <Txt size={14.5} lh={1.5}>
            {reason.text}
          </Txt>
          <View style={styles.evidence}>
            <Txt size={12.5}>{reason.evidence}</Txt>
          </View>
        </View>
      ))}
      <Txt size={13} weight={600} style={{ marginTop: 2 }}>
        Tweaks that would raise it
      </Txt>
      {r.tweaks.map((t) => (
        <View key={t.text} style={styles.tweak}>
          <Txt size={14} lh={1.5} style={{ flex: 1 }}>
            {t.text}
          </Txt>
          <Pill label={`+${t.gain.toFixed(2)}`} bg={colors.lavender} height={24} fontSize={12} />
        </View>
      ))}
      <Txt size={12} lh={1.5} color={colors.muted}>
        Estimate based on your history. Changes are to Curo’s idea score.
      </Txt>
      <CenterButton
        label="Develop this idea"
        height={48}
        fontSize={15.5}
        disabled={busy}
        onPress={() => develop(turn)}
      />
    </Appear>
  );
}

const styles = StyleSheet.create({
  hero: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 16,
    paddingHorizontal: 36,
    paddingVertical: 24,
  },
  heroMark: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: colors.lavender,
    alignItems: 'center',
    justifyContent: 'center',
  },
  thread: { padding: 20, paddingTop: 24, gap: 16 },
  card: { borderWidth: 1, borderColor: colors.gray, borderRadius: 22, padding: 16, gap: 10 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  evidence: {
    alignSelf: 'flex-start',
    backgroundColor: colors.gray,
    borderRadius: 11,
    paddingVertical: 4,
    paddingHorizontal: 10,
  },
  tweak: { flexDirection: 'row', alignItems: 'center', gap: 10 },
});
