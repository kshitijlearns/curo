'use client';
/** /admin/costs: this month's estimated spend per creator and per feature (admins only). */
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { BackHeader, ErrorNote, Loading } from '@/components/Chrome';
import { api, type S } from '@/lib/api';

export default function Costs() {
  const router = useRouter();
  const q = useQuery({ queryKey: ['costs'], queryFn: () => api<S['CostsOut']>('/admin/costs') });
  return (
    <div className="app">
      <BackHeader title="Costs" onBack={() => router.push('/settings')} sub={q.data ? `${q.data.month} · $${q.data.total_usd.toFixed(2)}` : null} />
      <main className="sheet" style={{ paddingBottom: 64 }}>
        {q.isLoading ? <Loading /> : null}
        {q.error ? <ErrorNote error={q.error} /> : null}
        {q.data ? (
          <>
            <h2 className="section-title">Per creator</h2>
            <p className="section-sub">Flagged above ${q.data.alert_usd.toFixed(2)} this month.</p>
            {q.data.creators.map((c) => (
              <div key={c.creator_id ?? 'none'} className={`card row between ${c.over_alert ? 'pink' : ''}`}>
                <span>
                  {c.username ? `@${c.username}` : 'System (no creator)'}
                  <br />
                  <span className="small muted">{c.calls} calls</span>
                </span>
                <strong>${c.cost_usd.toFixed(2)}</strong>
              </div>
            ))}
            <h2 className="section-title" style={{ marginTop: 20 }}>
              Per feature
            </h2>
            {q.data.features.map((f) => (
              <div key={`${f.provider}:${f.task}`} className="card row between">
                <span>
                  {f.task ?? 'other'} <span className="small muted">· {f.provider}</span>
                  <br />
                  <span className="small muted">{f.calls} calls</span>
                </span>
                <strong>${f.cost_usd.toFixed(2)}</strong>
              </div>
            ))}
          </>
        ) : null}
      </main>
    </div>
  );
}
