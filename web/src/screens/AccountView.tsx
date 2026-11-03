'use client';
/**
 * Account (v3): opened from Home's floating button. Who you are, what's left on your plan, what
 * you saved (drafts and opportunity areas) and the rest of the settings one tap away.
 */
import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { Icon, type IconName } from '@/components/Icon';
import type { Limit } from '@/lib/api';
import { useBilling, useMe } from '@/lib/hooks';
import { signOut } from '@/lib/session';
import { SavedView } from './SavedView';

const RES = [
  { key: 'project', label: 'Projects', icon: 'sparkle' },
  { key: 'simulation', label: 'Simulations', icon: 'simulator' },
  { key: 'chat', label: 'Ask Curo', icon: 'comments' },
] as const;

export function AccountView() {
  const router = useRouter();
  const me = useMe();
  const billing = useBilling();
  const a = me.data?.account;
  const handle = a?.username;
  const name = a?.full_name || (handle ? `@${handle}` : 'Your account');
  const initial = (handle ?? me.data?.email ?? '').replace('@', '').slice(0, 1).toUpperCase() || '·';
  const b = billing.data;
  const upgrade = () =>
    window.dispatchEvent(
      new CustomEvent<Limit>('curo:limit', {
        detail: { code: 'out_of_credits', plan: b?.plan ?? 'free', message: 'Pro gives you 10 projects, 10 simulations and 100 Ask Curo messages a month.' } as Limit,
      }),
    );
  return (
    <>
      <section className="profile">
        <span className="profile-avatar" aria-hidden="true">
          {initial}
        </span>
        <h1 className="display-title" style={{ fontSize: 34 }}>
          {name}
        </h1>
        {handle ? <span className="chip ink">@{handle}</span> : null}
        {a ? (
          <div className="stat-row">
            <Stat value={compact(a.followers)} label="followers" />
            <Stat value={compact(me.data?.reels)} label="reels read" />
            <Stat value={compact(a.posts)} label="posts" />
          </div>
        ) : null}
      </section>

      {b ? (
        <section className="card lemon plan" aria-label="Plan and credits">
          <div className="row between">
            <div>
              <span className="eyebrow">Your plan</span>
              <h2 className="block-title">{b.plan === 'pro' ? 'Pro' : 'Free'}</h2>
            </div>
            {b.plan !== 'pro' ? (
              <button className="btn small ink" onClick={upgrade}>
                <Icon name="bolt" size={16} strokeWidth={2} filled /> Go Pro
              </button>
            ) : (
              <span className="chip white">
                {b.status === 'cancelled' ? 'Ends' : 'Renews'} {fmtDay(b.period_end)}
              </span>
            )}
          </div>
          <div className="credit-grid">
            {RES.map((r) => {
              const c = b.credits[r.key];
              if (!c) return null;
              const share = c.plan_total ? c.plan_left / c.plan_total : 0;
              return (
                <div key={r.key} className="credit">
                  <Icon name={r.icon as IconName} size={18} strokeWidth={2} />
                  <b>{c.left}</b>
                  <span>{r.label} left</span>
                  <i className="credit-bar" aria-hidden="true">
                    <i style={{ width: `${Math.round(share * 100)}%` }} />
                  </i>
                </div>
              );
            })}
          </div>
          {b.plan !== 'pro' ? <p className="small" style={{ marginTop: 10 }}>Renews {fmtDay(b.period_end)} · top-ups never expire</p> : null}
        </section>
      ) : null}

      <h2 className="section-label">Saved</h2>
      <SavedView />

      <h2 className="section-label">More</h2>
      <div className="panel-block pink">
        <MenuRow href="/recaps" icon="play" label="All your recaps" />
        <MenuRow href="/settings" icon="gear" label="Plan, memory and settings" />
        <button
          className="pill-row"
          onClick={async () => {
            await signOut();
            router.replace('/login');
          }}
        >
          <span className="circle sm white" aria-hidden="true">
            <Icon name="back" size={16} strokeWidth={2} />
          </span>
          <span className="pill-row-main">
            <strong>Sign out</strong>
            {me.data?.email ? <small>{me.data.email}</small> : null}
          </span>
        </button>
      </div>
    </>
  );
}

function MenuRow({ href, icon, label }: { href: string; icon: IconName; label: string }) {
  return (
    <Link href={href} className="pill-row">
      <span className="circle sm white" aria-hidden="true">
        <Icon name={icon} size={16} strokeWidth={2} />
      </span>
      <span className="pill-row-main">
        <strong>{label}</strong>
      </span>
      <Icon name="chevronRight" size={18} strokeWidth={2} />
    </Link>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="stat">
      <b>{value}</b>
      <span>{label}</span>
    </div>
  );
}

export function compact(n: number | null | undefined) {
  if (n === null || n === undefined) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 10_000) return `${Math.round(n / 1000)}K`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

const fmtDay = (iso: string) => new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
