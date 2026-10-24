'use client';
/**
 * Step 5 of the first run (v2.1): "Save your recap and get a new one every month". An email
 * code turns the anonymous session into an account, keeping everything. "Maybe later" goes
 * to Home, which reminds them next time (unsaved accounts are deleted after 30 days).
 */
import { useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { DEMO } from '@/lib/demo';
import { LATER_KEY, saveAccount, sendSaveCode, usesSupabase } from '@/lib/session';



export default function Save() {
  const router = useRouter();
  const qc = useQueryClient();
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [sent, setSent] = useState(false);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const later = () => {
    try {
      sessionStorage.setItem(LATER_KEY, '1');
    } catch {
      /* private mode */
    }
    router.replace('/');
  };

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setDevCode(await sendSaveCode(email.trim()));
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Couldn’t send the code.');
    } finally {
      setBusy(false);
    }
  };
  const verify = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await saveAccount(email.trim(), code.trim());
      await qc.invalidateQueries();
      router.replace('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That code didn’t work.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="app">
      <header className="brand">
        <h1>Curo</h1>
      </header>
      <main className="sheet" style={{ paddingBottom: 48 }}>
        <h2 className="section-title" style={{ fontSize: 26 }}>
          Save your recap
        </h2>
        <p className="section-sub">
          …and get a new one every month. We’ll email you a 6-digit code: no password, and never your Instagram login.
        </p>
        {!sent ? (
          <form onSubmit={send} className="stack">
            <label htmlFor="email" className="sr-only">
              Email
            </label>
            <input
              id="email"
              className="field"
              type="email"
              autoComplete="email"
              inputMode="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <button className="btn block" disabled={busy || !email.includes('@')}>
              {busy ? 'Sending…' : 'Send code'}
            </button>
          </form>
        ) : (
          <form onSubmit={verify} className="stack">
            <p className="light">Code sent to {email}.</p>
            {devCode && !usesSupabase ? (
              <p className="label-sim" style={{ background: 'var(--lavender)' }}>
                {DEMO ? 'Demo with sample data' : 'Development sign-in'}: your code is {devCode}
              </p>
            ) : null}
            <label htmlFor="code" className="sr-only">
              Code
            </label>
            <input
              id="code"
              className="field"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="6-digit code"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              required
            />
            <button className="btn block" disabled={busy || code.length < 6}>
              {busy ? 'Saving…' : 'Save my account'}
            </button>
          </form>
        )}
        {error ? (
          <p role="alert" className="card pink" style={{ marginTop: 14 }}>
            {error}
          </p>
        ) : null}
        <button className="btn block ghost" style={{ marginTop: 14 }} onClick={later}>
          Maybe later
        </button>
        <p className="small muted" style={{ textAlign: 'center', marginTop: 12 }}>
          Accounts that aren’t saved are deleted after 30 days, with all their data.
        </p>
      </main>
    </div>
  );
}
