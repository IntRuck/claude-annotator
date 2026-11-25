const DEFAULT_LOW = 100;
const MAX_LOW = 100000;
const HEAT_RGB = '217, 119, 87'; // the accent colour
const BAD_ISSUES = ['errors', 'duplicates'];

/** The warn-below box as a whole number from 1 to 100000; empty or 0 means 100, like today. */
export function clampLow(raw) {
  const n = Math.round(Number(raw));
  if (!Number.isFinite(n) || n === 0) return DEFAULT_LOW;
  return Math.min(MAX_LOW, Math.max(1, n));
}

/** Most boxes / fewest boxes: over 10 is bad, over 3 is a warning (today's colours). */
export function imbalanceTone(ratio) {
  if (ratio > 10) return 'bad';
  return ratio > 3 ? 'warn' : '';
}

export function issueTone(issue) {
  if (!issue.count) return '';
  return BAD_ISSUES.includes(issue.key) ? 'bad' : 'warn';
}

/** Heatmap cell colour: darker for more box centres (square root, so a few boxes still show). Empty = plain. */
export function heatColour(value, max) {
  if (!value) return '';
  const alpha = Math.round((0.15 + 0.85 * Math.sqrt(value / max)) * 1000) / 1000;
  return `rgba(${HEAT_RGB}, ${alpha})`;
}

export function statusLine(status) {
  const parts = Object.entries(status).map(([name, count]) => `${name}: ${count}`);
  return parts.length ? parts.join(' · ') : 'none yet';
}
