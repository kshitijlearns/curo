'use client';
/**
 * Onboarding: the creator's public Instagram username — nothing else. CURO reads only public
 * data (no Instagram API, no login): the latest 50 reels, the newest 30 analysed in depth.
 */
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { Loading } from '@/components/Chrome';
import { api, type S } from '@/lib/api';
import { signedIn } from '@/lib/session';

export default function Onboarding() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [started, setStarted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    signedIn().then((ok) => !ok && router.replace('/login'));
  }, [router]);

  const status = useQuery({
    queryKey: ['onboarding'],
    queryFn: () => api<S['OnboardingStatus']>('/onboarding/status'),
    enabled: started,
    refetchInterval: (q) => (q.state.data?.status === 'ready' || q.state.data?.status === 'failed' ? false : 1500),
  });
  useEffect(() => {
    if (status.data?.status === 'ready') router.replace('/');
    if (status.data?.status === 'failed') {
      setError(status.data.error || status.data.message || 'Curo couldn’t read that account.');
      setStarted(false);
    }
  }, [status.data, router]);

  const start = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api<S['OnboardingStarted']>('/onboarding/username', { body: { username: name.trim() } });
      setStarted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Check the username and try again.');
    }
  };

  const st = status.data;
  return (
    <div className="app">
      <header className="brand">
        <h1>Curo</h1>
      </header>
      <main className="sheet" style={{ paddingBottom: 48 }}>
        <h2 className="section-title">Your Instagram username</h2>
        <p className="section-sub">
          Curo reads your public reels and comments. No Instagram login, no password — your account must be public.
        </p>
        {!started ? (
          <form onSubmit={start} className="stack">
            <label htmlFor="handle" className="sr-only">
              Instagram username
            </label>
            <input
              id="handle"
              className="field"
              placeholder="@yourname"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <button className="btn block" disabled={!name.trim()}>
              Continue
            </button>
          </form>
        ) : (
          <>
            <Loading text={st?.message || 'Reading your public reels…'} />
            {st ? (
              <div className="card gray">
                <p>
                  {st.reels_found} reels found · {st.reels_processed} analysed
                </p>
                <p className="small muted" style={{ marginTop: 6 }}>
                  Comments read on {st.comments_done} of {st.comments_total} reels
                </p>
              </div>
            ) : null}
          </>
        )}
        {error ? (
          <p role="alert" className="card pink" style={{ marginTop: 14 }}>
            {error}
          </p>
        ) : null}
      </main>
    </div>
  );
}
