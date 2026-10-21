import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated from 'react-native-reanimated';

import {
  keys,
  useOnboardingStatus,
  usePeers,
  useStartOnboarding,
  useTrackPeers,
} from '@/api/hooks';
import { ErrorNote, Field } from '@/components/Field';
import { Icon } from '@/components/Icon';
import { Appear } from '@/components/motion';
import { Finding, PeerRow } from '@/components/PeerList';
import { PlainScreen } from '@/components/PlainScreen';
import { Txt } from '@/components/Txt';
import { PrimaryButton, SkipLink } from '@/components/ui';
import { useSession } from '@/state/session';
import { colors, springOn } from '@/theme';

const PROMISES = [
  'Public data only: your public reels, their counts and comments.',
  'No Instagram login or password, ever.',
  'Private accounts can’t be used.',
];

/**
 * Username onboarding (logic doc §3): check the account is public, collect the profile
 * and latest reels, read comments on the newest ones. Home fills in as soon as reels exist.
 */
export default function Onboarding() {
  const [username, setUsername] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const start = useStartOnboarding();
  const status = useOnboardingStatus(submitted);
  const qc = useQueryClient();
  const signOut = useSession((s) => s.signOut);

  const s = status.data;
  // Resume a job already running (e.g. the app was reopened), or the one just started.
  const running =
    s?.status === 'running' || (submitted && (start.isPending || !s || s.status === 'not_started'));
  const ready = s?.status === 'ready' && (submitted || (s.reels_found ?? 0) > 0);
  const failed = submitted && s?.status === 'failed';

  useEffect(() => {
    if (!ready) return;
    qc.invalidateQueries({ queryKey: keys.me });
    if (submitted) return; // a fresh onboarding goes on to the peers step
    const t = setTimeout(() => router.replace('/'), 700);
    return () => clearTimeout(t);
  }, [ready, submitted, qc]);

  const submit = () =>
    start.mutate(username.trim(), {
      onSuccess: () => setSubmitted(true),
    });

  if (ready && submitted) return <PeersStep onDone={() => router.replace('/')} />;

  if (running || ready) {
    const step = String(s?.job?.progress?.step ?? 'profile');
    const order = ['profile', 'reels', 'comments', 'ready'];
    const at = ready ? 4 : Math.max(0, order.indexOf(step));
    const rows = [
      `Checking @${s?.username ?? username} is public`,
      `Collecting your latest reels${s?.reels_found ? ` · ${s.reels_found} found` : ''}`,
      `Reading comments on your newest reels${s?.comments_total ? ` · ${s.comments_done} of ${s.comments_total}` : ''}`,
      'Ready',
    ];
    return (
      <PlainScreen>
        <Txt size={20} weight={600}>
          Setting up @{s?.username ?? username}
        </Txt>
        <Txt size={14.5} lh={1.55} color={colors.muted}>
          Your first numbers appear in a moment. Curo keeps tracking every new reel from its first
          hours.
        </Txt>
        <View style={styles.steps}>
          {rows.map((label, k) => {
            const done = at > k || (k === 3 && ready);
            const cur = at === k;
            return (
              <View key={label} style={styles.stepRow}>
                <Animated.View
                  style={[
                    styles.dot,
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
                  style={{ flex: 1 }}
                >
                  {label}
                </Txt>
              </View>
            );
          })}
        </View>
      </PlainScreen>
    );
  }

  return (
    <PlainScreen>
      <Txt size={20} weight={600}>
        What’s your Instagram username?
      </Txt>
      <Field
        label="Instagram username"
        prefix="@"
        value={username}
        onChangeText={setUsername}
        placeholder="yourhandle"
        autoCapitalize="none"
        onSubmitEditing={submit}
      />
      <View style={{ gap: 10, marginVertical: 4 }}>
        {PROMISES.map((p) => (
          <View key={p} style={styles.promise}>
            <View style={styles.tick}>
              <Icon name="check" size={12} strokeWidth={2.8} color={colors.blue} />
            </View>
            <Txt size={14} lh={1.5} style={{ flex: 1 }}>
              {p}
            </Txt>
          </View>
        ))}
      </View>
      {failed ? <ErrorNote text={s?.error ?? 'Something went wrong. Try again.'} /> : null}
      {start.isError ? <ErrorNote text={start.error.message} /> : null}
      <PrimaryButton
        label="Continue"
        onPress={submit}
        disabled={!username.trim() || start.isPending}
      />
      {__DEV__ ? (
        <SkipLink
          label="Use the demo account (@curo.demo)"
          onPress={() => setUsername('curo.demo')}
        />
      ) : null}
      <SkipLink label="Sign out" onPress={() => signOut().then(() => router.replace('/login'))} />
    </PlainScreen>
  );
}

/**
 * Logic doc §3 step 5: CURO suggests likely peers and the creator confirms or replaces them.
 * "Creators you track", never "creators you follow" (Instagram doesn't expose that list).
 */
function PeersStep({ onDone }: { onDone: () => void }) {
  const peers = usePeers(true);
  const track = useTrackPeers();
  const [skipped, setSkipped] = useState<Set<string>>(new Set());
  const suggested = peers.data?.suggested ?? [];
  const chosen = suggested.filter((p) => !skipped.has(p.account_id));
  const toggle = (id: string) =>
    setSkipped((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const finding = peers.data?.finding ?? true;

  return (
    <PlainScreen>
      <Txt size={20} weight={600}>
        Creators you track
      </Txt>
      <Txt size={14.5} lh={1.55} color={colors.muted}>
        Curo compares your reels with creators like you to spot what’s working in your niche. Keep
        the ones that fit — you can add or remove creators any time in Settings.
      </Txt>
      {suggested.length === 0 ? (
        finding ? (
          <Finding text="Finding creators like you…" />
        ) : (
          <Txt size={14} lh={1.5}>
            No suggestions yet. You can add creators you know in Settings.
          </Txt>
        )
      ) : (
        <View style={{ gap: 10 }}>
          {suggested.map((p) => (
            <PeerRow
              key={p.account_id}
              peer={p}
              action="toggle"
              selected={!skipped.has(p.account_id)}
              onPress={() => toggle(p.account_id)}
            />
          ))}
        </View>
      )}
      {track.isError ? <ErrorNote text={track.error.message} /> : null}
      <PrimaryButton
        label={
          chosen.length
            ? `Track ${chosen.length} creator${chosen.length === 1 ? '' : 's'}`
            : 'Continue'
        }
        disabled={track.isPending}
        onPress={() =>
          chosen.length
            ? track.mutate({ account_ids: chosen.map((p) => p.account_id) }, { onSuccess: onDone })
            : onDone()
        }
      />
      {chosen.length ? <SkipLink label="Skip for now" onPress={onDone} /> : null}
    </PlainScreen>
  );
}

const styles = StyleSheet.create({
  steps: {
    backgroundColor: colors.gray,
    borderRadius: 24,
    paddingVertical: 6,
    paddingHorizontal: 18,
    marginTop: 6,
  },
  stepRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 11 },
  dot: {
    width: 26,
    height: 26,
    borderRadius: 13,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  promise: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  tick: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.lavender,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
});
