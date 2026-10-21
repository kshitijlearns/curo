import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import {
  useDeleteAccount,
  useDeleteMemory,
  useMe,
  useMemory,
  usePeers,
  useRemovePeer,
  useTrackPeers,
} from '@/api/hooks';
import { ErrorNote, Field } from '@/components/Field';
import { Icon } from '@/components/Icon';
import { Finding, PeerRow } from '@/components/PeerList';
import { CenterButton, OutlinePill, SkipLink } from '@/components/ui';
import { Press } from '@/components/motion';
import { PlainScreen } from '@/components/PlainScreen';
import { Eyebrow, Txt } from '@/components/Txt';
import { formatCount } from '@/lib/format';
import { useSession } from '@/state/session';
import { colors } from '@/theme';

/**
 * Settings (D17): the account, creators you track, what Curo remembers (logic doc §14:
 * "visible and deletable in settings"), sign-out and account deletion (logic doc §17).
 */
export default function Settings() {
  const me = useMe();
  const signOut = useSession((s) => s.signOut);
  const qc = useQueryClient();
  const account = me.data?.account;

  const back = () => (router.canGoBack() ? router.back() : router.replace('/'));

  return (
    <PlainScreen back={back} title="Settings">
      <View style={styles.card}>
        <Eyebrow color={colors.muted}>Instagram account</Eyebrow>
        <Txt size={18} weight={600}>
          @{me.data?.creator?.ig_username ?? '…'}
        </Txt>
        <Txt size={14} color={colors.muted}>
          {account?.followers != null ? `${formatCount(account.followers)} followers · ` : ''}
          {me.data?.reels ?? 0} reels collected · public counts only
        </Txt>
      </View>
      <View style={styles.card}>
        <Eyebrow color={colors.muted}>Signed in as</Eyebrow>
        <Txt size={15}>{me.data?.email ?? '…'}</Txt>
      </View>
      <TrackedCreators />
      <CuroMemory />
      <Row label="Check connection" onPress={() => router.push('/setup')} />
      <Row
        label="Sign out"
        onPress={async () => {
          qc.clear();
          await signOut();
          router.replace('/login');
        }}
      />
      <DeleteAccount handle={me.data?.creator?.ig_username ?? null} />
    </PlainScreen>
  );
}

/**
 * Delete the account and everything Curo holds about it (D106). Asked twice: the first tap
 * says what goes; only the second deletes.
 */
function DeleteAccount({ handle }: { handle: string | null }) {
  const [asking, setAsking] = useState(false);
  const del = useDeleteAccount();
  if (!asking) return <Row label="Delete account" onPress={() => setAsking(true)} />;
  return (
    <View style={styles.confirm}>
      <Txt size={17} weight={600}>
        Delete your account?
      </Txt>
      <Txt size={14} lh={1.55}>
        This deletes your sign-in, your drafts, simulations, chats and everything Curo remembers
        {handle
          ? `, plus everything it collected from @${handle}’s public reels. Curo also stops collecting @${handle}, and other creators can no longer track it in Curo`
          : ''}
        . It can’t be undone.
      </Txt>
      {del.isError ? <ErrorNote text={del.error.message} /> : null}
      <CenterButton
        label={del.isPending ? 'Deleting…' : 'Delete my account'}
        color={colors.ink}
        disabled={del.isPending}
        onPress={() => del.mutate(undefined, { onSuccess: () => router.replace('/login') })}
      />
      <SkipLink label="Keep my account" onPress={() => setAsking(false)} />
    </View>
  );
}

/** Creators you track (logic doc §3): the creator always has the final say. */
function TrackedCreators() {
  const peers = usePeers();
  const track = useTrackPeers();
  const remove = useRemovePeer();
  const [handle, setHandle] = useState('');
  const tracked = peers.data?.tracked ?? [];
  const suggested = peers.data?.suggested ?? [];
  const add = () =>
    handle.trim() && track.mutate({ username: handle.trim() }, { onSuccess: () => setHandle('') });

  return (
    <View style={{ gap: 10, marginTop: 6 }}>
      <Txt size={17} weight={600}>
        Creators you track
      </Txt>
      <Txt size={13.5} lh={1.5} color={colors.muted}>
        Curo compares your reels with these public accounts to find what’s working in your niche.
      </Txt>
      {tracked.length === 0 ? (
        <Txt size={14} lh={1.5}>
          You’re not tracking anyone yet.
        </Txt>
      ) : null}
      {tracked.map((p) => (
        <PeerRow
          key={p.account_id}
          peer={p}
          action="remove"
          onPress={() => remove.mutate(p.account_id)}
        />
      ))}
      {suggested.length ? <Eyebrow color={colors.muted}>Suggested for you</Eyebrow> : null}
      {suggested.map((p) => (
        <PeerRow
          key={p.account_id}
          peer={p}
          action="track"
          onPress={() => track.mutate({ account_ids: [p.account_id] })}
        />
      ))}
      <Field
        label="Add a creator by username"
        prefix="@"
        value={handle}
        onChangeText={setHandle}
        placeholder="their public handle"
        autoCapitalize="none"
        onSubmitEditing={add}
      />
      {track.isPending && handle ? (
        <Finding text={`Checking @${handle.replace('@', '')} is public…`} />
      ) : null}
      {track.isError ? <ErrorNote text={track.error.message} /> : null}
      <SkipLink label="Add creator" onPress={add} />
    </View>
  );
}

/** What Curo remembers: what the creator told it, and what it learned from their behaviour. */
function CuroMemory() {
  const memory = useMemory();
  const remove = useDeleteMemory();
  const items = memory.data ?? [];
  return (
    <View style={{ gap: 10, marginTop: 6 }}>
      <Txt size={17} weight={600}>
        What Curo remembers
      </Txt>
      <Txt size={13.5} lh={1.5} color={colors.muted}>
        Curo uses these when it suggests ideas, writes scripts and answers you. Delete anything you
        don’t want it to keep.
      </Txt>
      {memory.isSuccess && items.length === 0 ? (
        <Txt size={14} lh={1.5}>
          Nothing yet. Tell Curo things like “never suggest dance trends” in any chat and they’ll
          appear here.
        </Txt>
      ) : null}
      {items.map((m) => (
        <View key={m.id} style={styles.memory}>
          <View style={{ flex: 1, gap: 3 }}>
            <Eyebrow color={colors.muted}>{m.source === 'stated' ? 'You said' : 'Learned'}</Eyebrow>
            <Txt size={14.5} lh={1.45}>
              {m.value}
            </Txt>
          </View>
          <OutlinePill
            label="Delete"
            disabled={remove.isPending}
            onPress={() => remove.mutate(m.id)}
          />
        </View>
      ))}
      {remove.isError ? <ErrorNote text={remove.error.message} /> : null}
    </View>
  );
}

function Row({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Press onPress={onPress} accessibilityLabel={label} style={styles.row}>
      <Txt size={15.5} weight={600} style={{ flex: 1 }}>
        {label}
      </Txt>
      <Icon name="chevronRight" size={18} color={colors.blue} strokeWidth={2} />
    </Press>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.gray, borderRadius: 22, padding: 16, gap: 4 },
  confirm: { backgroundColor: colors.pink, borderRadius: 22, padding: 16, gap: 10 },
  memory: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderWidth: 1,
    borderColor: colors.gray,
    borderRadius: 20,
    padding: 14,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.gray,
    borderRadius: 22,
    paddingVertical: 16,
    paddingHorizontal: 16,
  },
});
