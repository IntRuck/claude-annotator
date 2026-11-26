const MIN = 60_000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

/** "just now", "5 min ago", "2 h ago", "yesterday", "3 days ago", then the date. */
export function timeAgo(iso, now = Date.now()) {
  const ms = now - new Date(iso).getTime();
  if (ms < MIN) return 'just now';
  if (ms < HOUR) return `${Math.floor(ms / MIN)} min ago`;
  if (ms < DAY) return `${Math.floor(ms / HOUR)} h ago`;
  if (ms < 2 * DAY) return 'yesterday';
  if (ms < 7 * DAY) return `${Math.floor(ms / DAY)} days ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

/** The full date and time, for a tooltip. */
export const fullDate = (iso) => new Date(iso).toLocaleString();
