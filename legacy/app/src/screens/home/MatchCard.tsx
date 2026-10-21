import { StyleSheet, View } from 'react-native';

import { useDecideMatch, useMatches } from '@/api/hooks';
import { ErrorNote } from '@/components/Field';
import { Appear } from '@/components/motion';
import { Eyebrow, Txt } from '@/components/Txt';
import { CenterButton, OutlinePill } from '@/components/ui';
import { useApp } from '@/state/app';
import { colors } from '@/theme';

/**
 * A new reel that looks like one the creator simulated or drafted (logic doc §15 step 2:
 * "asks the creator to confirm the match", D108). Confirmed, Home's arrow compares the reel
 * with its simulation and the accuracy record counts it. One at a time, newest first.
 */
export function MatchCard() {
  const matches = useMatches();
  const decide = useDecideMatch();
  const showToast = useApp((s) => s.showToast);
  const match = matches.data?.[0];
  if (!match) return null;

  const fromSim = !!match.simulation_id;
  const answer = (confirm: boolean) =>
    decide.mutate(
      { id: match.id, confirm },
      {
        onSuccess: () =>
          showToast(
            !confirm
              ? 'Got it. Curo won’t link them.'
              : fromSim
                ? 'Linked. Its arrow now compares the reel with your simulation.'
                : 'Linked to your draft.',
          ),
      },
    );

  return (
    <Appear kind="fade">
      <View style={styles.card} accessibilityLabel="Confirm a posted reel">
        <Eyebrow color={colors.muted}>Just posted</Eyebrow>
        <Txt size={16.5} weight={600} lh={1.4}>
          {fromSim
            ? `Is “${match.reel_title}” the reel you simulated?`
            : `Did “${match.reel_title}” come from your draft${match.project_title ? ` “${match.project_title}”` : ''}?`}
        </Txt>
        {(match.reasons ?? []).map((r) => (
          <Txt key={r} size={13.5} lh={1.5} color={colors.muted}>
            {r}
          </Txt>
        ))}
        {decide.isError ? <ErrorNote text={decide.error.message} /> : null}
        <View style={styles.actions}>
          <CenterButton
            label="Yes, that’s it"
            height={44}
            fontSize={15}
            disabled={decide.isPending}
            onPress={() => answer(true)}
            style={{ flex: 1 }}
          />
          <OutlinePill
            label="No"
            height={44}
            fontSize={15}
            disabled={decide.isPending}
            onPress={() => answer(false)}
          />
        </View>
      </View>
    </Appear>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.gray,
    borderRadius: 22,
    padding: 16,
    gap: 8,
    marginBottom: 20,
  },
  actions: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 4 },
});
