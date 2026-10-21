/**
 * Sign-in: an email one-time code.
 *
 * With NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY set, Supabase Auth sends the
 * code and keeps the session (supabase-js). Without them, the backend's local stub does the
 * same in development (POST /v1/auth/otp → /v1/auth/verify; the code is shown on screen).
 * Either way the API receives a bearer token it verifies itself. Never an Instagram login.
 */
import type { SupabaseClient } from '@supabase/supabase-js';

import { DEMO } from './demo';

const KEY = 'curo.session';
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const SUPABASE_ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

export const usesSupabase = !DEMO && Boolean(SUPABASE_URL && SUPABASE_ANON);

let client: SupabaseClient | null = null;
async function supabase(): Promise<SupabaseClient> {
  if (!client) {
    const { createClient } = await import('@supabase/supabase-js');
    client = createClient(SUPABASE_URL, SUPABASE_ANON, {
      auth: { persistSession: true, autoRefreshToken: true },
    });
  }
  return client;
}

type Local = { token: string; email: string | null; expires: number };

function readLocal(): Local | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as Local;
    return s.expires > Date.now() ? s : null;
  } catch {
    return null;
  }
}

export async function getToken(): Promise<string | null> {
  if (usesSupabase) {
    const { data } = await (await supabase()).auth.getSession();
    return data.session?.access_token ?? null;
  }
  return readLocal()?.token ?? null;
}

export async function signedIn(): Promise<boolean> {
  return Boolean(await getToken());
}

/** Send the code. Returns the code itself only from the local development stub. */
export async function sendCode(email: string): Promise<string | null> {
  if (usesSupabase) {
    const { error } = await (await supabase()).auth.signInWithOtp({
      email,
      options: { shouldCreateUser: true },
    });
    if (error) throw new Error(error.message);
    return null;
  }
  if (DEMO) return '123456'; // the demo signs anyone in as the demo creator
  const res = await fetch('/api/v1/auth/otp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) throw new Error('Couldn’t send the code. Check the email address.');
  return (await res.json()).dev_code ?? null;
}

export async function verifyCode(email: string, code: string): Promise<void> {
  if (usesSupabase) {
    const { error } = await (await supabase()).auth.verifyOtp({ email, token: code, type: 'email' });
    if (error) throw new Error('That code didn’t work. Check it, or send a new one.');
    return;
  }
  if (DEMO) {
    window.localStorage.setItem(KEY, JSON.stringify({ token: 'demo', email, expires: Date.now() + 86_400_000 }));
    return;
  }
  const res = await fetch('/api/v1/auth/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, code }),
  });
  if (!res.ok) throw new Error('That code didn’t work. Check it, or send a new one.');
  const s = await res.json();
  window.localStorage.setItem(
    KEY,
    JSON.stringify({ token: s.access_token, email: s.email, expires: Date.now() + s.expires_in * 1000 }),
  );
}

export async function signOut(): Promise<void> {
  if (usesSupabase) await (await supabase()).auth.signOut();
  if (typeof window !== 'undefined') window.localStorage.removeItem(KEY);
}
