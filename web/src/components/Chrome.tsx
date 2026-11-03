'use client';
/**
 * The shell's chrome (v3): the top bar (wordmark or back), the floating dark Nav with three tabs
 * (Home, Studio, Simulator) and, on Home, the round Account button beside it; the toast.
 */
import { Icon, type IconName } from './Icon';
import type { Tab } from '@/state/app';

export function Wordmark() {
  return (
    <span className="wordmark" aria-label="Curo">
      <i aria-hidden="true" />
      curo
    </span>
  );
}

export function TopBar({ right }: { right?: React.ReactNode }) {
  return (
    <header className="topbar">
      <Wordmark />
      <div className="row" style={{ gap: 8 }}>
        {right}
      </div>
    </header>
  );
}

/** Kept for the standalone pages (settings, recaps): the wordmark row. */
export function BrandHeader() {
  return <TopBar />;
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
      <div className="row between">
        <button className="circle" onClick={onBack} aria-label="Back">
          <Icon name="back" size={20} strokeWidth={2} />
        </button>
        <span className="back-title">{title}</span>
        {bookmark ? (
          <button
            className={`circle${bookmark.saved ? ' ink' : ''}`}
            onClick={bookmark.onToggle}
            aria-pressed={bookmark.saved}
            aria-label={bookmark.saved ? 'Remove from saved' : 'Save for later'}
          >
            <Icon name="bookmark" size={18} strokeWidth={2} filled={bookmark.saved} />
          </button>
        ) : (
          <span style={{ width: 44 }} />
        )}
      </div>
      {sub ? <p className="sub">{sub}</p> : null}
    </header>
  );
}

const TABS: { id: Tab; label: string; icon: IconName }[] = [
  { id: 'home', label: 'Home', icon: 'home' },
  { id: 'studio', label: 'Studio', icon: 'sparkle' },
  { id: 'sim', label: 'Simulator', icon: 'simulator' },
];

/**
 * The floating Nav: a dark capsule; the open tab grows into a coloured pill with its name, the
 * others are white circles. On Home, the Account button floats beside it.
 */
export function Nav({
  active,
  onNav,
  account,
}: {
  active: Tab;
  onNav: (t: Tab) => void;
  account?: { initial: string; open: boolean; badge: number; onOpen: () => void } | null;
}) {
  return (
    <div className="nav-row">
      <nav className="nav" aria-label="Main">
        <div className="nav-bar" role="tablist">
          {TABS.map((t) => {
            const on = t.id === active; // Account opens over Home, so Home stays lit
            return (
              <button
                key={t.id}
                role="tab"
                aria-selected={on}
                aria-label={t.label}
                className={`nav-item nav-${t.id}${on ? ' on' : ''}`}
                onClick={() => onNav(t.id)}
              >
                <Icon name={t.icon} size={21} strokeWidth={2} />
                <span className="nav-label">{t.label}</span>
              </button>
            );
          })}
        </div>
      </nav>
      {account ? (
        <button
          className={`account-fab${account.open ? ' on' : ''}`}
          onClick={account.onOpen}
          aria-label={`Your account${account.badge ? `, ${account.badge} saved` : ''}`}
          aria-pressed={account.open}
        >
          <span className="account-initial">{account.initial}</span>
          {account.badge > 0 ? (
            <span className="badge" key={account.badge}>
              {account.badge}
            </span>
          ) : null}
        </button>
      ) : null}
    </div>
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
      <span className="loader" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      <span>{text}</span>
    </div>
  );
}

export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof Error ? error.message : 'Something went wrong.';
  return (
    <div className="card coral" role="alert">
      <p>{msg}</p>
      {onRetry ? (
        <button className="btn small" style={{ marginTop: 12 }} onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}

/** The round ↗ on a coloured card. */
export function Arrow({ dark = false, icon = 'arrowUpRight' }: { dark?: boolean; icon?: IconName }) {
  return (
    <span className={`arrow${dark ? ' dark' : ''}`} aria-hidden="true">
      <Icon name={icon} size={18} strokeWidth={2.2} />
    </span>
  );
}

/** A small "step" chip on a block: "Stage 1", "Trend", "0:04". */
export function Chip({ children, tone = 'white' }: { children: React.ReactNode; tone?: 'white' | 'ink' | 'clear' }) {
  return <span className={`chip ${tone}`}>{children}</span>;
}
