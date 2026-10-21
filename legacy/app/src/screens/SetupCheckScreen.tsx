import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { apiBaseUrl } from '@/api/config';
import { fetchHealth, type Health } from '@/api/health';
import { colors, font } from '@/theme';

type Result = { attempt: number; health: Health | null; error: string | null };

/**
 * Phase 0 only: proves the phone reaches the API and shows the stack's health.
 * Replaced by Home in Phase 1.
 */
export function SetupCheckScreen() {
  const insets = useSafeAreaInsets();
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchHealth().then(
      (health) => !cancelled && setResult({ attempt, health, error: null }),
      (e: unknown) =>
        !cancelled &&
        setResult({ attempt, health: null, error: e instanceof Error ? e.message : String(e) }),
    );
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const loading = result?.attempt !== attempt;
  const health = loading ? null : result.health;
  const error = loading ? null : result.error;
  const load = () => setAttempt((n) => n + 1);

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + 22 }]}>
        <Text style={styles.brand}>Curo</Text>
      </View>
      <ScrollView
        style={styles.sheet}
        contentContainerStyle={[styles.sheetContent, { paddingBottom: insets.bottom + 28 }]}
      >
        <Text style={styles.h2}>Setup check</Text>
        <Text style={styles.muted}>API at {apiBaseUrl()}</Text>

        {loading ? (
          <ActivityIndicator color={colors.blue} style={{ marginTop: 24 }} />
        ) : error ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Can’t reach the API</Text>
            <Text style={styles.body}>{error}</Text>
            <Text style={styles.muted}>
              Is the stack running (make dev / ./dev.ps1 dev), and is the phone on the same Wi-Fi?
            </Text>
          </View>
        ) : health ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>
              API {health.version} · {health.status === 'ok' ? 'healthy' : 'not ready'}
            </Text>
            {Object.entries(health.checks).map(([name, check]) => (
              <View key={name} style={styles.row}>
                <View
                  style={[styles.dot, { backgroundColor: check.ok ? colors.blue : colors.pink }]}
                />
                <Text style={styles.rowName}>{name}</Text>
                <Text style={styles.rowDetail} numberOfLines={2}>
                  {check.detail}
                </Text>
              </View>
            ))}
            <Text style={styles.muted}>
              Mock mode {health.mock_mode ? 'on' : 'off'} · clock {health.clock.now.slice(0, 16)}
            </Text>
          </View>
        ) : null}

        <Pressable
          onPress={load}
          style={({ pressed }) => [styles.button, pressed && { transform: [{ scale: 0.96 }] }]}
        >
          <Text style={styles.buttonText}>Check again</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.lavender },
  header: { paddingHorizontal: 20, paddingBottom: 52 },
  brand: { ...font(600), fontSize: 34, letterSpacing: -0.7, color: colors.ink },
  sheet: {
    flex: 1,
    marginTop: -32,
    backgroundColor: colors.white,
    borderTopLeftRadius: 32,
    borderTopRightRadius: 32,
  },
  sheetContent: { padding: 20, paddingTop: 24, gap: 12 },
  h2: { ...font(600), fontSize: 20, color: colors.ink },
  muted: { ...font(400), fontSize: 13, lineHeight: 19, color: colors.muted },
  card: { backgroundColor: colors.gray, borderRadius: 26, padding: 18, gap: 10 },
  cardTitle: { ...font(600), fontSize: 16, color: colors.ink },
  body: { ...font(400), fontSize: 14.5, lineHeight: 22, color: colors.ink },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  dot: { width: 10, height: 10, borderRadius: 5 },
  rowName: { ...font(600), fontSize: 14, color: colors.ink, width: 84 },
  rowDetail: { ...font(400), fontSize: 13, color: colors.muted, flex: 1 },
  button: {
    marginTop: 8,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.blue,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonText: { ...font(600), fontSize: 17, color: colors.white },
});
