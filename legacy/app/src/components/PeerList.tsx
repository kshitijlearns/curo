import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { Icon } from './Icon';
import { Press } from './motion';
import { Txt } from './Txt';
import type { Schemas } from '@/api/client';
import { formatCount } from '@/lib/format';
import { colors } from '@/theme';

type Peer = Schemas['Peer'];

/** A row per creator: @handle, size and why they were suggested, with a toggle or remove. */
export function PeerRow({
  peer,
  selected,
  onPress,
  action,
}: {
  peer: Peer;
  selected?: boolean;
  onPress: () => void;
  action: 'toggle' | 'remove' | 'track';
}) {
  const followers = peer.followers != null ? `${formatCount(peer.followers)} followers` : null;
  const reasons = [followers, ...(peer.reasons ?? [])].filter(Boolean).join(' · ');
  const label =
    action === 'remove'
      ? `Stop tracking @${peer.username}`
      : action === 'track'
        ? `Track @${peer.username}`
        : `${selected ? 'Unselect' : 'Select'} @${peer.username}`;
  return (
    <Press
      onPress={onPress}
      accessibilityLabel={label}
      accessibilityState={action === 'toggle' ? { checked: selected } : undefined}
      style={styles.row}
    >
      <View style={styles.avatar}>
        <Txt size={15} weight={600}>
          {peer.username.charAt(0).toUpperCase()}
        </Txt>
      </View>
      <View style={{ flex: 1, gap: 2 }}>
        <Txt size={15} weight={600}>
          @{peer.username}
        </Txt>
        {reasons ? (
          <Txt size={12.5} color={colors.muted}>
            {reasons}
          </Txt>
        ) : null}
      </View>
      {action === 'toggle' ? (
        <View
          style={[
            styles.check,
            {
              backgroundColor: selected ? colors.blue : colors.white,
              borderColor: selected ? colors.blue : colors.lavender,
            },
          ]}
        >
          {selected ? <Icon name="check" size={13} strokeWidth={3} color={colors.white} /> : null}
        </View>
      ) : action === 'remove' ? (
        <Txt size={13} weight={600} color={colors.blue}>
          Remove
        </Txt>
      ) : (
        <Txt size={13} weight={600} color={colors.blue}>
          Track
        </Txt>
      )}
    </Press>
  );
}

export function Finding({ text }: { text: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8 }}>
      <ActivityIndicator color={colors.blue} />
      <Txt size={14} color={colors.muted}>
        {text}
      </Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderWidth: 1,
    borderColor: colors.gray,
    borderRadius: 20,
    paddingVertical: 12,
    paddingHorizontal: 14,
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.lavender,
    alignItems: 'center',
    justifyContent: 'center',
  },
  check: {
    width: 26,
    height: 26,
    borderRadius: 13,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
