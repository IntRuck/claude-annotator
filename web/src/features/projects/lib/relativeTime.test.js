import { describe, expect, it } from 'vitest';
import { timeAgo } from './relativeTime';

const NOW = new Date('2026-11-25T12:00:00Z').getTime();
const ago = (ms) => new Date(NOW - ms).toISOString();
const MIN = 60_000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

describe('timeAgo', () => {
  it('says "just now" under a minute', () => {
    expect(timeAgo(ago(20_000), NOW)).toBe('just now');
  });

  it('counts minutes, then hours', () => {
    expect(timeAgo(ago(5 * MIN), NOW)).toBe('5 min ago');
    expect(timeAgo(ago(2 * HOUR + 10 * MIN), NOW)).toBe('2 h ago');
  });

  it('says "yesterday", then days up to a week', () => {
    expect(timeAgo(ago(DAY + HOUR), NOW)).toBe('yesterday');
    expect(timeAgo(ago(3 * DAY), NOW)).toBe('3 days ago');
  });

  it('gives the date after a week', () => {
    const iso = ago(30 * DAY);
    expect(timeAgo(iso, NOW)).toBe(new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }));
  });

  it('treats a time slightly in the future (clock skew) as just now', () => {
    expect(timeAgo(ago(-5000), NOW)).toBe('just now');
  });
});
