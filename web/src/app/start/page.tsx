'use client';
/**
 * Step 1 of the first run (v2.1): "What's your Instagram username?" — the very first screen.
 * A session starts right away, before any email (anonymous); the account is saved later.
 * Public profiles only: CURO never asks for an Instagram password or login.
 */
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { ApiError, api, type S } from '@/lib/api';
import { DEMO } from '@/lib/demo';
import { startAnonymous } from '@/lib/session';

const VALID = /^[a-z0-9._]{1,30}$/;

function clean(v: string) {
  let s = v.trim().toLowerCase().replace(/^@/, '');
  if (s.includes('instagram.com/')) s = s.replace(/\/+$/, '').split('/').pop() ?? s;
  return s;
}

export default function Start() {
  const router = useRouter();
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [taken, setTaken] = useState(false);

  const handle = clean(value);
  const problem =
    value && !VALID.test(handle)
      ? handle.includes(' ')
        ? 'Usernames have no spaces.'
        : handle.length > 30
          ? 'That’s longer than an Instagram username (30 characters).'
          : 'Use letters, numbers, dots and underscores.'
      : null;

  const go = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!handle || problem) return;
    setBusy(true);
    setError(null);
    setTaken(false);
    try {
      await startAnonymous();
      await api<S['OnboardingStarted']>('/onboarding/username', { body: { username: handle } });
      router.push('/welcome');
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setTaken(true);
        setError(`@${handle} is already on CURO.`);
      } else {
        setError(err instanceof Error ? err.message : 'Something went wrong. Try again.');
      }
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
          What’s your Instagram username?
        </h2>
        <p className="section-sub">
          CURO reads your public profile and reels to build your first Creator Recap. No Instagram login, ever.
        </p>
        {DEMO ? (
          <p className="label-sim" style={{ background: 'var(--lavender)' }}>
            This is a demo with sample data: any username shows the demo creator, @curo.demo.
          </p>
        ) : null}
        <form onSubmit={go} className="stack" noValidate>
          <label htmlFor="handle" className="sr-only">
            Instagram username
          </label>
          <div className="handle-field">
            <span aria-hidden="true" style={{ fontWeight: 600 }}>
              @
            </span>
            <input
              id="handle"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="yourname"
              autoCapitalize="none"
              autoCorrect="off"
              autoComplete="off"
              spellCheck={false}
              inputMode="text"
              aria-invalid={!!problem}
              aria-describedby="handle-help"
              autoFocus
            />
          </div>
          <p id="handle-help" className="small" style={{ margin: '0 8px', minHeight: 18, color: problem ? 'var(--ink)' : 'var(--muted)' }}>
            {problem ?? 'Your account must be public.'}
          </p>
          <button className="btn block" style={{ height: 56, fontSize: 18 }} disabled={busy || !handle || !!problem}>
            {busy ? 'Starting…' : 'Continue'}
          </button>
        </form>
        {error ? (
          <div className="card pink" role="alert" style={{ marginTop: 14 }}>
            <p>{error}</p>
            {taken ? (
              <Link href="/login" className="btn small" style={{ marginTop: 12 }}>
                Sign in instead
              </Link>
            ) : null}
          </div>
        ) : null}
        <p className="small muted" style={{ textAlign: 'center', marginTop: 28 }}>
          Already have an account? <Link href="/login">Sign in</Link>
        </p>
      </main>
    </div>
  );
}
