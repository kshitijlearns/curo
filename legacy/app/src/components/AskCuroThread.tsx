import { StyleSheet, View } from 'react-native';

import { Appear, TypingDots } from './motion';
import { Txt } from './Txt';
import { CuroMark, UserBubble } from './ui';
import { sourceLabel } from '@/api/chat';
import { useApp, type ChatMsg } from '@/state/app';
import { colors } from '@/theme';

const EMPTY: ChatMsg[] = [];

/**
 * Ask Curo's conversation on one screen (logic doc §14): the creator's messages, and Curo's
 * replies as they stream in, each with the records it drew on.
 */
export function AskCuroThread({ threadKey }: { threadKey: string | null }) {
  const msgs = useApp((s) => (threadKey ? s.chat[threadKey] : undefined)) ?? EMPTY;
  if (!msgs.length) return null;
  return (
    <View style={styles.thread} accessibilityLabel="Ask Curo conversation">
      {msgs.map((m) =>
        m.role === 'user' ? (
          <Appear key={m.id}>
            <UserBubble text={m.text} fontSize={14.5} />
          </Appear>
        ) : (
          <Appear key={m.id}>
            <CuroReply m={m} />
          </Appear>
        ),
      )}
    </View>
  );
}

function CuroReply({ m }: { m: ChatMsg }) {
  const waiting = m.pending && !m.text;
  return (
    <View style={styles.row}>
      <CuroMark size={28} />
      <View style={{ flex: 1, gap: 8 }}>
        <View style={[styles.bubble, m.failed && { backgroundColor: colors.pink }]}>
          {waiting ? (
            <View style={{ gap: 2 }}>
              {m.activity ? (
                <Txt size={13} color={colors.muted}>
                  {m.activity}
                </Txt>
              ) : null}
              <TypingDots />
            </View>
          ) : (
            <Txt size={14} lh={1.55}>
              {m.text}
            </Txt>
          )}
        </View>
        {m.sources?.length ? (
          <View style={styles.sources} accessibilityLabel="Sources">
            {m.sources.map((s) => (
              <View key={`${s.kind}:${s.id ?? s.title}`} style={styles.source}>
                <Txt size={11.5} weight={600} numberOfLines={1}>
                  {sourceLabel(s)}
                </Txt>
              </View>
            ))}
          </View>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  thread: { gap: 12, marginTop: 18 },
  row: { flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
  bubble: {
    alignSelf: 'flex-start',
    maxWidth: '100%',
    backgroundColor: colors.gray,
    borderRadius: 22,
    borderBottomLeftRadius: 6,
    paddingVertical: 11,
    paddingHorizontal: 14,
  },
  sources: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  source: {
    maxWidth: '100%',
    height: 26,
    paddingHorizontal: 10,
    borderRadius: 13,
    borderWidth: 1,
    borderColor: colors.lavender,
    backgroundColor: colors.white,
    justifyContent: 'center',
  },
});
