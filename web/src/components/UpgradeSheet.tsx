'use client';
/** Shown whenever the API answers 402: what ran out, and the way to get more. */
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { Overlay } from '@/components/Overlay';
import { Icon } from './Icon';
import { api, type Limit, type S } from '@/lib/api';

const TOPUP: Record<string, 'topup_project' | 'topup_simulation' | 'topup_chat'> = {
  project: 'topup_project',
  simulation: 'topup_simulation',
  chat: 'topup_chat',
};

export function UpgradeSheet({ limit, onClose }: { limit: Limit; onClose: () => void }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  const buy = async (item: S['CheckoutIn']['item']) => {
    setBusy(true);
    try {
      const out = await api<S['CheckoutOut']>('/billing/checkout', { body: { item } });
      if (out.url) window.location.assign(out.url);
      else {
        setDone(item === 'pro' ? 'You’re on Pro now.' : 'Top-up added. It never expires.');
        qc.invalidateQueries({ queryKey: ['billing'] });
      }
    } catch (e) {
      setDone(e instanceof Error ? e.message : 'That didn’t go through.');
    } finally {
      setBusy(false);
    }
  };

  const credits = limit.code === 'out_of_credits';
  return (
    <Overlay labelledBy="upgrade-title" onClose={onClose}>
        <div className="row between">
          <h2 id="upgrade-title" style={{ margin: 0, fontSize: 22 }}>
            {credits ? 'You’ve reached this month’s limit' : 'Limit reached'}
          </h2>
          <button className="circle sm" onClick={onClose} aria-label="Close">
            <Icon name="close" size={18} />
          </button>
        </div>
        <p className="light" style={{ fontSize: 16, margin: '12px 0 20px' }}>
          {limit.message}
        </p>
        {done ? (
          <div className="card lav">
            <p>{done}</p>
            <button className="btn block" style={{ marginTop: 14 }} onClick={onClose}>
              Continue
            </button>
          </div>
        ) : credits ? (
          <div className="stack">
            {limit.plan !== 'pro' ? (
              <div className="card lav">
                <h3>Pro · $30 a month</h3>
                <p className="light">10 projects and 10 simulations a month, 100 Ask Curo messages.</p>
                <button className="btn block" style={{ marginTop: 14 }} disabled={busy} onClick={() => buy('pro')}>
                  Upgrade to Pro
                </button>
              </div>
            ) : null}
            {limit.resource && TOPUP[limit.resource] ? (
              <div className="card">
                <h3>Top up · about $1.50</h3>
                <p className="light">
                  {limit.resource === 'chat' ? '20 more Ask Curo messages' : `One more ${limit.resource}`}. Top-ups never
                  expire.
                </p>
                <button
                  className="btn block ghost"
                  style={{ marginTop: 14 }}
                  disabled={busy}
                  onClick={() => buy(TOPUP[limit.resource!])}
                >
                  Buy a top-up
                </button>
              </div>
            ) : null}
            <p className="small muted" style={{ textAlign: 'center' }}>
              Your plan’s credits come back at the start of each month.
            </p>
          </div>
        ) : (
          <button className="btn block" onClick={onClose}>
            OK
          </button>
        )}
    </Overlay>
  );
}
