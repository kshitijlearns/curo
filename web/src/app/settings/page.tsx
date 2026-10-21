'use client';
/** Settings: plan and credits, what Curo remembers, sign out, and delete the account. */
import { QueryClient, QueryClientProvider, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { BackHeader, ErrorNote, Loading } from '@/components/Chrome';
import { UpgradeSheet } from '@/components/UpgradeSheet';
import { api, type Limit, type S } from '@/lib/api';
import { useBilling, useMe, useMemory } from '@/lib/hooks';
import { signOut, signedIn } from '@/lib/session';

export default function Settings() {
  const router = useRouter();
  useEffect(() => {
    signedIn().then((ok) => !ok && router.replace('/login'));
  }, [router]);
  return (
    <div className="app">
      <BackHeader title="Settings" onBack={() => router.push('/')} />
      <main className="sheet" style={{ paddingBottom: 64 }}>
        <Body />
      </main>
    </div>
  );
}

const RES = { project: 'Projects', simulation: 'Simulations', chat: 'Ask Curo messages' } as const;

function Body() {
  const router = useRouter();
  const qc = useQueryClient();
  const me = useMe();
  const billing = useBilling();
  const memory = useMemory();
  const [limit, setLimit] = useState<Limit | null>(null);
  const [confirm, setConfirm] = useState('');

  const cancel = useMutation({
    mutationFn: () => api<S['BillingOut']>('/billing/cancel', { body: {} }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['billing'] }),
  });
  const forget = useMutation({
    mutationFn: (id: string) => api<void>(`/memory/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['memory'] }),
  });
  const del = useMutation({
    mutationFn: () => api<S['DeletionStarted']>('/me', { method: 'DELETE' }),
    onSuccess: async () => {
      await signOut();
      router.replace('/login');
    },
  });

  const b = billing.data;
  const handle = me.data?.account?.username;
  return (
    <>
      <h2 className="section-title">Account</h2>
      <div className="card">
        <p>
          <strong>{handle ? `@${handle}` : 'No Instagram username yet'}</strong>
        </p>
        <p className="small muted" style={{ marginTop: 4 }}>
          {me.data?.email}
        </p>
        <button
          className="btn small ghost"
          style={{ marginTop: 12 }}
          onClick={async () => {
            await signOut();
            router.replace('/login');
          }}
        >
          Sign out
        </button>
      </div>

      <h2 className="section-title" style={{ marginTop: 20 }}>
        Plan and credits
      </h2>
      {billing.isLoading ? <Loading /> : null}
      {billing.error ? <ErrorNote error={billing.error} onRetry={() => billing.refetch()} /> : null}
      {b ? (
        <div className="card lav">
          <div className="row between">
            <h3 style={{ margin: 0 }}>{b.plan === 'pro' ? 'Pro' : 'Free'}</h3>
            <span className="small">
              {b.status === 'cancelled' ? 'Ends' : 'Renews'}{' '}
              {new Date(b.period_end).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
            </span>
          </div>
          {(Object.keys(RES) as (keyof typeof RES)[]).map((r) => {
            const c = b.credits[r];
            if (!c) return null;
            return (
              <div key={r} style={{ marginTop: 12 }}>
                <div className="row between small">
                  <span>{RES[r]}</span>
                  <span>
                    {c.left} left{c.topup_left ? ` (${c.topup_left} top-up)` : ''}
                  </span>
                </div>
                <div className="bar" style={{ marginTop: 4, background: 'var(--white)' }}>
                  <span style={{ width: `${c.plan_total ? Math.round((c.plan_left / c.plan_total) * 100) : 0}%` }} />
                </div>
              </div>
            );
          })}
          <p className="small" style={{ marginTop: 12 }}>
            Each project includes up to {b.revisions_per_project} revisions; each simulation up to{' '}
            {b.agent_messages_per_simulation} agent messages. Top-ups never expire.
          </p>
          <div className="row wrap" style={{ marginTop: 14 }}>
            {b.plan !== 'pro' ? (
              <button className="btn small" onClick={() => setLimit({ code: 'out_of_credits', plan: b.plan, message: 'Pro gives you 10 projects, 10 simulations and 100 Ask Curo messages a month.' })}>
                Upgrade to Pro
              </button>
            ) : b.status !== 'cancelled' ? (
              <button className="btn small ghost" onClick={() => cancel.mutate()} disabled={cancel.isPending}>
                Cancel Pro
              </button>
            ) : null}
            <button
              className="btn small ghost"
              onClick={() => setLimit({ code: 'out_of_credits', resource: 'simulation', plan: 'pro', message: 'Add credits that never expire.' })}
            >
              Buy a top-up
            </button>
          </div>
        </div>
      ) : null}

      <h2 className="section-title" style={{ marginTop: 20 }}>
        What Curo remembers
      </h2>
      <p className="section-sub">Preferences you told Ask Curo, and lessons from your edits. Delete any of them.</p>
      {memory.data?.length === 0 ? <p className="empty">Nothing yet.</p> : null}
      {memory.data?.map((m) => (
        <div key={m.id} className="card row between">
          <span>
            {m.value}
            <br />
            <span className="small muted">{m.source === 'stated' ? 'You said this' : 'Learned from your edits'}</span>
          </span>
          <button className="pill" onClick={() => forget.mutate(m.id)} aria-label={`Forget: ${m.value}`}>
            Forget
          </button>
        </div>
      ))}

      <AdminLink />

      <h2 className="section-title" style={{ marginTop: 20 }}>
        Delete your account
      </h2>
      <div className="card pink">
        <p>
          Deletes your account, drafts, simulations, chats and the data Curo collected for you. Your username stays on a
          do-not-collect list. This can’t be undone.
        </p>
        <label htmlFor="confirm" className="small" style={{ display: 'block', margin: '12px 0 6px' }}>
          Type DELETE to confirm
        </label>
        <input id="confirm" className="field" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        <button
          className="btn block"
          style={{ marginTop: 12, background: 'var(--ink)' }}
          disabled={confirm !== 'DELETE' || del.isPending}
          onClick={() => del.mutate()}
        >
          {del.isPending ? 'Deleting…' : 'Delete my account'}
        </button>
      </div>
      {limit ? <UpgradeSheet limit={limit} onClose={() => setLimit(null)} /> : null}
    </>
  );
}

function AdminLink() {
  const [admin, setAdmin] = useState(false);
  useEffect(() => {
    api('/admin/costs')
      .then(() => setAdmin(true))
      .catch(() => setAdmin(false));
  }, []);
  if (!admin) return null;
  return (
    <Link href="/admin/costs" className="card tap" style={{ textDecoration: 'none', marginTop: 20 }}>
      <h3 style={{ margin: 0 }}>Costs (admin)</h3>
      <p className="small muted">Spend per creator and feature this month.</p>
    </Link>
  );
}

// Keeps the import list honest for tree-shaking (QueryClient types are used by providers).
export type _Unused = QueryClient | typeof QueryClientProvider;
