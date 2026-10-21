import { StyleSheet, TextInput, View, type TextInputProps } from 'react-native';

import { Txt } from './Txt';
import { colors, font } from '@/theme';

/** A text field in the Composer's pill style, with an optional fixed prefix (e.g. "@"). */
export function Field({
  prefix,
  label,
  ...props
}: TextInputProps & { prefix?: string; label: string }) {
  return (
    <View style={styles.pill}>
      {prefix ? (
        <Txt size={16} weight={600} color={colors.muted}>
          {prefix}
        </Txt>
      ) : null}
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={colors.muted}
        autoCorrect={false}
        style={styles.input}
        {...props}
      />
    </View>
  );
}

/** A short error line in a pink box. */
export function ErrorNote({ text }: { text: string }) {
  return (
    <View style={styles.error} accessibilityRole="alert">
      <Txt size={14} lh={1.5}>
        {text}
      </Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    height: 56,
    paddingHorizontal: 20,
    borderRadius: 28,
    backgroundColor: colors.gray,
  },
  input: { ...font(400), flex: 1, height: 48, fontSize: 16, color: colors.ink, padding: 0 },
  error: {
    backgroundColor: colors.pink,
    borderRadius: 20,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
});
