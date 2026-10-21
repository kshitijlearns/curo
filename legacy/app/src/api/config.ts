import Constants from 'expo-constants';

export const API_PORT = 8000;

/**
 * Where the CURO API lives.
 *
 * 1. EXPO_PUBLIC_API_BASE_URL, when set (staging, production, or a tunnel).
 * 2. Otherwise the dev machine Expo is served from: Expo Go on the phone loads the
 *    bundle from <dev-machine-ip>:8081, and the API runs on the same machine at :8000.
 */
export function apiBaseUrl(
  env: string | undefined = process.env.EXPO_PUBLIC_API_BASE_URL,
  hostUri: string | undefined = Constants.expoConfig?.hostUri,
): string {
  if (env && env.trim()) return env.trim().replace(/\/+$/, '');
  const host = hostUri ? hostUri.split(':')[0] : '';
  return `http://${host || 'localhost'}:${API_PORT}`;
}
