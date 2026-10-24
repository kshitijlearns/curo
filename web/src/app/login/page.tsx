'use client';
/** Sign in with an email code. Never an Instagram login or password. */
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { DEMO } from '@/lib/demo';
import { sendCode, usesSupabase, verifyCode } from '@/lib/session';

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [sent, setSent] = useState(false);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setDevCode(await sendCode(email.trim()));
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
      await verifyCode(email.trim(), code.trim());
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
        <h2 className="section-title">Sign in</h2>
        <p className="section-sub">
          We’ll email you a 6-digit code. Curo never asks for your Instagram password.
        </p>
        {DEMO ? (
          <p className="label-sim" style={{ background: 'var(--lavender)' }}>
            This is a demo with sample data for @curo.demo. Sign in with any email.
          </p>
        ) : null}
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
              {busy ? 'Checking…' : 'Sign in'}
            </button>
            <button type="button" className="btn block ghost" onClick={() => setSent(false)}>
              Use a different email
            </button>
          </form>
        )}
        {error ? (
          <p role="alert" className="card pink" style={{ marginTop: 14 }}>
            {error}
          </p>
        ) : null}
        <p className="small muted" style={{ textAlign: 'center', marginTop: 28 }}>
          New to CURO? <a href="/start">Start with your Instagram username</a>
        </p>
      </main>
    </div>
  );
}
