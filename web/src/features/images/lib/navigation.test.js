import { describe, expect, it } from 'vitest';
import { positionOf, stepFrom } from './navigation';

const list = [{ id: 10 }, { id: 20 }, { id: 30 }];

describe('stepFrom (same rule as today\'s A/D keys)', () => {
  it('moves forward and back within the list', () => {
    expect(stepFrom(list, 20, 1)).toBe(30);
    expect(stepFrom(list, 20, -1)).toBe(10);
  });

  it('stays on the first or last image at the ends', () => {
    expect(stepFrom(list, 10, -1)).toBe(10);
    expect(stepFrom(list, 30, 1)).toBe(30);
  });

  it('jumps to the first image when the current one is not in the list', () => {
    expect(stepFrom(list, 99, 1)).toBe(10);
    expect(stepFrom(list, null, -1)).toBe(10);
  });

  it('returns null for an empty list', () => {
    expect(stepFrom([], 10, 1)).toBeNull();
  });
});

describe('positionOf', () => {
  it('is 1-based, or null when the image is not in the list', () => {
    expect(positionOf(list, 20)).toBe(2);
    expect(positionOf(list, 99)).toBeNull();
  });
});
