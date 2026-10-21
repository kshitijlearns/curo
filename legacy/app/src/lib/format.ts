/**
 * Number and time formatting in the prototype's style: 504, 1.2K, 90K, 1.3M.
 * `null` (a count that isn't public) is shown as a dash, never as 0.
 */
export function formatCount(n: number | null | undefined): string | null {
  if (n == null) return null;
  if (n < 1000) return String(n);
  if (n < 10_000) return `${trimZero((n / 1000).toFixed(1))}K`;
  if (n < 1_000_000) return `${Math.round(n / 1000)}K`;
  return `${trimZero((n / 1_000_000).toFixed(1))}M`;
}

function trimZero(s: string): string {
  return s.endsWith('.0') ? s.slice(0, -2) : s;
}

/** 32 → "0:32", 75.4 → "1:15". */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return '';
  const s = Math.round(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

/** "Updated 2 hours ago" relative to `now` (CURO's clock on the server side). */
export function updatedAgo(iso: string | null | undefined, now: Date = new Date()): string | null {
  if (!iso) return null;
  const hours = (now.getTime() - new Date(iso).getTime()) / 3_600_000;
  if (hours < 1) return 'Updated less than an hour ago';
  if (hours < 24) {
    const h = Math.floor(hours);
    return `Updated ${h} hour${h === 1 ? '' : 's'} ago`;
  }
  const d = Math.floor(hours / 24);
  return `Updated ${d} day${d === 1 ? '' : 's'} ago`;
}
