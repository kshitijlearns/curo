'use client';
/** All recaps: the first ("your story so far") and every month since. */
import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { BackHeader, ErrorNote, Loading } from '@/components/Chrome';
import { useRecaps } from '@/lib/hooks';

export default function Recaps() {
  const router = useRouter();
  const q = useRecaps();
  return (
    <div className="app">
      <BackHeader title="All recaps" onBack={() => router.push('/')} sub="A new one arrives at the start of every month." />
      <main className="sheet" style={{ paddingBottom: 64 }}>
        {q.isLoading ? <Loading /> : null}
        {q.error ? <ErrorNote error={q.error} onRetry={() => q.refetch()} /> : null}
        {q.data?.length === 0 ? <p className="empty">Your first recap is on its way.</p> : null}
        {q.data?.map((r, i) => (
          <Link key={r.id} href={`/recap?id=${r.id}`} className={`card tap ${i === 0 ? 'lav' : ''}`}>
            <div className="row between">
              <h3 style={{ margin: 0 }}>{r.period_label}</h3>
              {r.is_new ? <span className="new-badge">New</span> : null}
            </div>
            <p className="light" style={{ marginTop: 6 }}>
              {[r.creator_level, r.archetype].filter(Boolean).join(' · ')}
            </p>
            <div className="row wrap" style={{ gap: 6, marginTop: 10 }}>
              {(r.stats ?? []).slice(0, 3).map((s) => (
                <span key={s.slide} className="pill white">
                  {s.value} {s.label}
                </span>
              ))}
            </div>
          </Link>
        ))}
      </main>
    </div>
  );
}
