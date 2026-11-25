import { describe, expect, it } from 'vitest';
import { clampLow, heatColour, imbalanceTone, issueTone, statusLine } from './healthView';

describe('healthView', () => {
  it('reads the warn-below box as a whole number from 1 to 100000, else 100 (like today)', () => {
    expect(clampLow('25')).toBe(25);
    expect(clampLow('')).toBe(100);
    expect(clampLow('0')).toBe(100);
    expect(clampLow('abc')).toBe(100);
    expect(clampLow('-3')).toBe(1);
    expect(clampLow('2.6')).toBe(3);
    expect(clampLow('999999')).toBe(100000);
  });

  it('colours imbalance: over 10 is bad, over 3 is a warning', () => {
    expect(imbalanceTone(11)).toBe('bad');
    expect(imbalanceTone(4)).toBe('warn');
    expect(imbalanceTone(3)).toBe('');
  });

  it('colours issues: errors and duplicates are bad, others warnings, none found is plain', () => {
    expect(issueTone({ key: 'errors', count: 2 })).toBe('bad');
    expect(issueTone({ key: 'duplicates', count: 1 })).toBe('bad');
    expect(issueTone({ key: 'tiny', count: 1 })).toBe('warn');
    expect(issueTone({ key: 'errors', count: 0 })).toBe('');
  });

  it('shades heatmap cells darker for more boxes, and leaves empty cells plain', () => {
    expect(heatColour(0, 4)).toBe('');
    expect(heatColour(4, 4)).toBe('rgba(217, 119, 87, 1)');
    expect(heatColour(1, 4)).toBe('rgba(217, 119, 87, 0.575)');
  });

  it('lists the image statuses in one line', () => {
    expect(statusLine({ auto: 3, error: 1 })).toBe('auto: 3 · error: 1');
    expect(statusLine({})).toBe('none yet');
  });
});
