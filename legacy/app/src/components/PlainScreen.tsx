import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { BackHeader } from './Header';
import { Txt } from './Txt';
import { PrimaryButton } from './ui';
import { colors } from '@/theme';

/**
 * The prototype's shell without the dock: lavender header, white rounded sheet.
 * Used by Login, Onboarding and Settings (screens the prototype doesn't draw, D17).
 */
export function PlainScreen({
  children,
  back,
  title,
}: {
  children: React.ReactNode;
  back?: () => void;
  title?: string;
}) {
  const insets = useSafeAreaInsets();
  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      {back ? (
        <BackHeader topInset={insets.top} title={title ?? ''} onBack={back} />
      ) : (
        <View style={[styles.brand, { paddingTop: 22 + insets.top }]}>
          <Txt size={34} weight={600} ls={-0.02} style={{ lineHeight: 36 }}>
            Curo
          </Txt>
        </View>
      )}
      <ScrollView
        style={styles.sheet}
        contentContainerStyle={[styles.content, { paddingBottom: 28 + insets.bottom }]}
        keyboardShouldPersistTaps="handled"
      >
        {children}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

export function LoadingScreen() {
  return (
    <PlainScreen>
      <ActivityIndicator color={colors.blue} style={{ marginTop: 40 }} />
    </PlainScreen>
  );
}

export function MessageScreen({
  title,
  text,
  action,
}: {
  title: string;
  text: string;
  action?: { label: string; onPress: () => void };
}) {
  return (
    <PlainScreen>
      <Txt size={20} weight={600}>
        {title}
      </Txt>
      <Txt size={14.5} lh={1.55} color={colors.muted}>
        {text}
      </Txt>
      {action ? (
        <PrimaryButton label={action.label} onPress={action.onPress} style={{ marginTop: 8 }} />
      ) : null}
    </PlainScreen>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.lavender },
  brand: { paddingHorizontal: 20, paddingBottom: 52 },
  sheet: {
    flex: 1,
    marginTop: -32,
    backgroundColor: colors.white,
    borderTopLeftRadius: 32,
    borderTopRightRadius: 32,
  },
  content: { paddingHorizontal: 20, paddingTop: 24, gap: 12 },
});
