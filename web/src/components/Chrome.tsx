'use client';
/** The shell's chrome: the lavender header (brand or back), the springy Nav and the toast. */
import Link from 'next/link';

import { Icon } from './Icon';
import type { Tab } from '@/state/app';

export function BrandHeader({
  savedCount,
  onSaved,
  initial,
}: {
  savedCount: number;
  onSaved: () => void;
  initial?: string | null;
}) {
  return (
    <header className="brand">
      <h1>Curo</h1>
      <div className="row" style={{ gap: 10 }}>
        <button className="circle" onClick={onSaved} aria-label="Saved opportunities and drafts">
          <Icon name="bookmark" size={20} />
          {savedCount > 0 ? (
            <span className="badge" key={savedCount}>
              {savedCount}
            </span>
          ) : null}
        </button>
        <Link href="/settings" className="circle blue" aria-label="Account and settings">
          <span style={{ fontWeight: 600, fontSize: 17 }}>
            {(initial ?? '').replace('@', '').slice(0, 1).toUpperCase() || '·'}
          </span>
        </Link>
      </div>
    </header>
  );
}

export function BackHeader({
  title,
  onBack,
  sub,
  bookmark,
}: {
  title: string;
  onBack: () => void;
  sub?: string | null;
  bookmark?: { saved: boolean; onToggle: () => void };
}) {
  return (
    <header className="back-header">
      <div className="row">
        <button className="circle sm" onClick={onBack} aria-label="Back">
          <Icon name="back" size={20} strokeWidth={1.8} />
        </button>
        <h1>{title}</h1>
        {bookmark ? (
          <button
            className={`circle sm${bookmark.saved ? ' blue' : ''}`}
            onClick={bookmark.onToggle}
            aria-pressed={bookmark.saved}
            aria-label={bookmark.saved ? 'Remove from saved' : 'Save for later'}
            style={{ transform: bookmark.saved ? 'scale(1.08)' : undefined }}
          >
            <Icon name="bookmark" size={18} strokeWidth={1.8} filled={bookmark.saved} />
          </button>
        ) : (
          <span style={{ width: 44 }} />
        )}
      </div>
      {sub ? <p className="sub">{sub}</p> : null}
    </header>
  );
}

const ITEMS: { id: Tab; label: string; icon: 'home' | 'studio' | 'simulator' }[] = [
  { id: 'home', label: 'Home', icon: 'home' },
  { id: 'studio', label: 'Studio', icon: 'studio' },
  { id: 'sim', label: 'Simulator', icon: 'simulator' },
];

/** The active tab's icon grows into a blue circle that springs up out of the bar. */
export function Nav({ active, onNav }: { active: Tab; onNav: (t: Tab) => void }) {
  return (
    <nav className="nav" aria-label="Main">
      <div className="nav-bar" role="tablist">
        {ITEMS.map((it) => (
          <button
            key={it.id}
            role="tab"
            aria-selected={it.id === active}
            className="nav-item"
            onClick={() => onNav(it.id)}
          >
            <span className="nav-circle">
              <Icon name={it.icon} size={22} strokeWidth={it.id === 'sim' ? 1.8 : 1.7} />
            </span>
            {it.label}
          </button>
        ))}
      </div>
    </nav>
  );
}

export function Toast({ text }: { text: string }) {
  return (
    <div className="toast" role="status" aria-live="polite">
      {text}
    </div>
  );
}

export function Loading({ text = 'Loading…' }: { text?: string }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{text}</span>
    </div>
  );
}

export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof Error ? error.message : 'Something went wrong.';
  return (
    <div className="card pink" role="alert">
      <p>{msg}</p>
      {onRetry ? (
        <button className="btn small ghost" style={{ marginTop: 12 }} onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}
