import { describe, expect, it } from 'vitest';
import {
  MIN_DOTS, boundsOf, hitDot, hitEdge, insertDot, insideOutline, moveOutline, outlineCount, removeDot, withOutline,
  withoutOutline,
} from './outline';

const IMG = { iw: 200, ih: 100 };
const VIEW = { scale: 1, ox: 0, oy: 0 }; // stage pixel = fraction * image size
const TRIANGLE = [[0.1, 0.1], [0.5, 0.1], [0.3, 0.5]];

describe('outline shape', () => {
  it('its box is the smallest box around the dots', () => {
    expect(boundsOf(TRIANGLE)).toEqual({ x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5 });
    expect(withOutline({ cls: 2, source: 'ai' }, TRIANGLE)).toEqual({
      cls: 2, source: 'ai', points: TRIANGLE, x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5,
    });
  });

  it('removing the outline keeps the same box', () => {
    const plain = withoutOutline(withOutline({ cls: 0 }, TRIANGLE));
    expect(plain).toEqual({ cls: 0, x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5 });
    expect('points' in plain).toBe(false);
  });

  it('a point is inside the outline, not just inside its box', () => {
    expect(insideOutline(TRIANGLE, [0.3, 0.2])).toBe(true);
    expect(insideOutline(TRIANGLE, [0.12, 0.45])).toBe(false); // inside the box, outside the triangle
  });

  it('counts the outlined objects', () => {
    expect(outlineCount([withOutline({ cls: 0 }, TRIANGLE), { cls: 0, x1: 0, y1: 0, x2: 1, y2: 1 }])).toBe(1);
  });
});

describe('finding dots and lines under the pointer', () => {
  it('finds the dot within grab distance', () => {
    expect(hitDot(TRIANGLE, [22, 12], VIEW, IMG)).toBe(0); // dot 0 is at (20, 10)
    expect(hitDot(TRIANGLE, [60, 30], VIEW, IMG)).toBe(-1); // between the dots
  });

  it('finds the line between two dots, including the one closing back to the first', () => {
    expect(hitEdge(TRIANGLE, [60, 12], VIEW, IMG)).toBe(0);  // on the line from (20,10) to (100,10)
    expect(hitEdge(TRIANGLE, [40, 32], VIEW, IMG)).toBe(2);  // on the line from (60,50) back to (20,10)
    expect(hitEdge(TRIANGLE, [60, 30], VIEW, IMG)).toBe(-1); // inside, far from every line
  });

  it('adds a dot after a line start and removes one, never below 3 dots', () => {
    expect(insertDot(TRIANGLE, 0, [0.3, 0.1])).toEqual([[0.1, 0.1], [0.3, 0.1], [0.5, 0.1], [0.3, 0.5]]);
    expect(removeDot([...TRIANGLE, [0.1, 0.5]], 3)).toEqual(TRIANGLE);
    expect(MIN_DOTS).toBe(3);
    expect(removeDot(TRIANGLE, 1)).toBeNull();
  });
});

describe('moveOutline', () => {
  it('moves every dot and the box together', () => {
    const moved = moveOutline(withOutline({ cls: 0 }, TRIANGLE), 0.1, 0.2);
    expect(moved.points).toEqual([[expect.closeTo(0.2), expect.closeTo(0.3)], [expect.closeTo(0.6), expect.closeTo(0.3)],
      [expect.closeTo(0.4), expect.closeTo(0.7)]]);
    expect(moved).toMatchObject({ x1: expect.closeTo(0.2), y1: expect.closeTo(0.3), x2: expect.closeTo(0.6), y2: expect.closeTo(0.7) });
  });

  it('stops at the image edge and keeps the shape', () => {
    const near = withOutline({ cls: 0 }, [[0.8, 0.1], [0.95, 0.1], [0.9, 0.3]]);
    const moved = moveOutline(near, 0.2, 0);
    expect(moved.points.map(([x]) => x)).toEqual([expect.closeTo(0.85), expect.closeTo(1), expect.closeTo(0.95)]);
    expect(moved.x2).toBeCloseTo(1);
  });
});
