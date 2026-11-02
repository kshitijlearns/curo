'use client';
/** The shell's chrome: the header (brand or back), the floating Nav and the toast. */
import Link from 'next/link';

import { Icon } from './Icon';
import type { Tab } from '@/state/app';

export function BrandHeader({ initial }: { initial?: string | null }) {
  return (
    <header className="brand">
      <h1>Curo</h1>
      <Link href="/settings" className="circle violet" aria-label="Account and settings">
        <span style={{ fontWeight: 600, fontSize: 17 }}>
          {(initial ?? '').replace('@', '').slice(0, 1).toUpperCase() || '·'}
        </span>
      </Link>
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
            className={`circle sm${bookmark.saved ? ' violet' : ''}`}
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

/** A floating pill: Home, Saved, the raised Studio button, Simulator and You. */
export function Nav({
  active,
  saved,
  savedCount,
  onNav,
  onSaved,
}: {
  active: Tab;
  saved: boolean;
  savedCount: number;
  onNav: (t: Tab) => void;
  onSaved: () => void;
}) {
  const on = (t: Tab) => !saved && t === active;
  return (
    <nav className="nav" aria-label="Main">
      <div className="nav-bar" role="tablist">
        <button role="tab" aria-selected={on('home')} className="nav-item" onClick={() => onNav('home')}>
          <Icon name="home" size={22} />
          Home
        </button>
        <button role="tab" aria-selected={saved} className="nav-item" onClick={onSaved} aria-label="Saved opportunities and drafts">
          <Icon name="bookmark" size={22} />
          {savedCount > 0 ? (
            <span className="badge" key={savedCount}>
              {savedCount}
            </span>
          ) : null}
          Saved
        </button>
        <button role="tab" aria-selected={on('studio')} className="nav-fab" onClick={() => onNav('studio')}>
          <span>
            <Icon name="sparkle" size={26} />
          </span>
          Studio
        </button>
        <button role="tab" aria-selected={on('sim')} className="nav-item" onClick={() => onNav('sim')}>
          <Icon name="simulator" size={22} strokeWidth={1.8} />
          Simulator
        </button>
        <Link href="/settings" className="nav-item" role="tab" aria-selected={false}>
          <Icon name="user" size={22} />
          You
        </Link>
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
    <div className="card mist" role="alert">
      <p>{msg}</p>
      {onRetry ? (
        <button className="btn small ghost" style={{ marginTop: 12 }} onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}
