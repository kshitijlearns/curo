/**
 * The signed-in session: the API token, kept in the phone's secure storage
 * (expo-secure-store; localStorage on web, which is only used for visual checks).
 */
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { create } from 'zustand';

const KEY = 'curo.session';

export type Session = { token: string; email: string | null };

type SessionState = {
  hydrated: boolean;
  session: Session | null;
  hydrate: () => Promise<void>;
  signIn: (session: Session) => Promise<void>;
  signOut: () => Promise<void>;
};

const storage = {
  async get(): Promise<string | null> {
    if (Platform.OS === 'web') return globalThis.localStorage?.getItem(KEY) ?? null;
    return SecureStore.getItemAsync(KEY);
  },
  async set(value: string): Promise<void> {
    if (Platform.OS === 'web') globalThis.localStorage?.setItem(KEY, value);
    else await SecureStore.setItemAsync(KEY, value);
  },
  async clear(): Promise<void> {
    if (Platform.OS === 'web') globalThis.localStorage?.removeItem(KEY);
    else await SecureStore.deleteItemAsync(KEY);
  },
};

export const useSession = create<SessionState>()((set) => ({
  hydrated: false,
  session: null,
  hydrate: async () => {
    let session: Session | null = null;
    try {
      const raw = await storage.get();
      session = raw ? (JSON.parse(raw) as Session) : null;
    } catch {
      session = null;
    }
    set({ hydrated: true, session });
  },
  signIn: async (session) => {
    await storage.set(JSON.stringify(session));
    set({ session });
  },
  signOut: async () => {
    await storage.clear();
    set({ session: null });
  },
}));
