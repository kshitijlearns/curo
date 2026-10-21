import { useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';
import Animated, { type CSSAnimationKeyframes } from 'react-native-reanimated';

import { Icon } from './Icon';
import { Txt } from './Txt';
import { useVoiceInput, type VoiceProblem } from '@/lib/voice';
import { colors, font, springOn } from '@/theme';

const VOICE_MESSAGES: Record<VoiceProblem, string> = {
  unavailable: 'Voice input needs the CURO app build. For now, use the mic on your keyboard.',
  permission: 'Curo needs microphone access for voice input. You can allow it in Settings.',
  failed: 'Voice input didn’t work this time. Try again, or type instead.',
};

const WAVE: CSSAnimationKeyframes = {
  '0%': { transform: [{ scaleY: 0.25 }] },
  '50%': { transform: [{ scaleY: 1 }] },
  '100%': { transform: [{ scaleY: 0.25 }] },
};

const PULSE: CSSAnimationKeyframes = {
  from: { opacity: 0.45, transform: [{ scale: 1 }] },
  to: { opacity: 0, transform: [{ scale: 72 / 44 }] },
};

type Props = {
  placeholder: string;
  hint?: string;
  busy?: boolean;
  onSend: (text: string) => void;
  /** Shows a short message (voice unavailable, permission denied…). */
  onNotice?: (message: string) => void;
};

/** Chat + voice composer (prototype Composer). */
export function Composer({ placeholder, hint, busy = false, onSend, onNotice }: Props) {
  const [text, setText] = useState('');
  const voice = useVoiceInput(
    (spoken) => setText((t) => (t.trim() ? `${t.trim()} ${spoken}` : spoken)),
    (problem) => onNotice?.(VOICE_MESSAGES[problem]),
  );
  const canSend = !!text.trim() && !busy;

  const submit = () => {
    const value = text.trim();
    if (!value || busy) return;
    onSend(value);
    setText('');
  };

  const toggleMic = () => (voice.listening ? voice.stop() : voice.start());

  return (
    <View style={styles.wrap}>
      {hint ? (
        <Txt size={13.5} lh={1.45} color={colors.muted} style={{ marginHorizontal: 4 }}>
          {hint}
        </Txt>
      ) : null}
      <View style={styles.pill}>
        {voice.listening ? (
          <View style={styles.listening}>
            <View style={styles.bars}>
              {Array.from({ length: 14 }, (_, i) => (
                <Animated.View
                  key={i}
                  style={[
                    styles.bar,
                    {
                      backgroundColor: i % 3 === 1 ? colors.blue : colors.ink,
                      animationName: WAVE,
                      animationDuration: 900,
                      animationDelay: (i * 97) % 900,
                      animationTimingFunction: 'ease-in-out',
                      animationIterationCount: 'infinite',
                    },
                  ]}
                />
              ))}
            </View>
            <Txt size={13} numberOfLines={1} style={{ flex: 1 }}>
              {voice.partial || 'Listening…'}
            </Txt>
          </View>
        ) : (
          <TextInput
            accessibilityLabel="Message Curo"
            value={text}
            onChangeText={setText}
            onSubmitEditing={submit}
            placeholder={placeholder}
            placeholderTextColor={colors.muted}
            returnKeyType="send"
            submitBehavior="submit"
            style={styles.input}
          />
        )}

        <View style={styles.micWrap}>
          {voice.listening ? (
            <Animated.View
              pointerEvents="none"
              style={[
                styles.pulse,
                {
                  animationName: PULSE,
                  animationDuration: 1200,
                  animationTimingFunction: 'ease-out',
                  animationIterationCount: 'infinite',
                },
              ]}
            />
          ) : null}
          <Pressable
            onPress={toggleMic}
            accessibilityRole="button"
            accessibilityLabel={voice.listening ? 'Stop voice input' : 'Speak instead of typing'}
            accessibilityState={{ selected: voice.listening }}
          >
            <Animated.View
              style={[
                styles.mic,
                {
                  backgroundColor: voice.listening ? colors.ink : 'rgba(36,36,36,0)',
                  transform: [{ scale: voice.listening ? 1.06 : 1 }],
                },
                springOn('backgroundColor', 'transform'),
              ]}
            >
              <Icon name="mic" size={21} color={voice.listening ? colors.white : colors.ink} />
            </Animated.View>
          </Pressable>
        </View>

        <Pressable
          onPress={submit}
          disabled={!canSend}
          accessibilityRole="button"
          accessibilityLabel="Send"
          accessibilityState={{ disabled: !canSend }}
        >
          <Animated.View
            style={[
              styles.send,
              { opacity: canSend ? 1 : 0.4, transform: [{ scale: canSend ? 1 : 0.9 }] },
              springOn('opacity', 'transform'),
            ]}
          >
            <Icon name="arrowRight" size={20} color={colors.white} strokeWidth={2} />
          </Animated.View>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 8 },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    height: 56,
    paddingLeft: 20,
    paddingRight: 5,
    borderRadius: 28,
    backgroundColor: colors.gray,
  },
  input: {
    ...font(400),
    flex: 1,
    minWidth: 0,
    height: 44,
    fontSize: 15,
    color: colors.ink,
    padding: 0,
  },
  listening: { flex: 1, minWidth: 0, flexDirection: 'row', alignItems: 'center', gap: 10 },
  bars: { flexDirection: 'row', alignItems: 'center', gap: 3, height: 26 },
  bar: { width: 3, height: 22, borderRadius: 2 },
  micWrap: { width: 44, height: 44 },
  pulse: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    borderRadius: 22,
    backgroundColor: colors.blue,
  },
  mic: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  send: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: colors.blue,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
