import { describe, expect, it } from 'vitest';
import { fitView, hitBox, hitCorner, moveBox, newBox, normalizeBox, resizeBox, toImage, toStage, zoomAt } from './geometry';

const IMG = { iw: 200, ih: 100 };
const box = (x1, y1, x2, y2, cls = 0) => ({ cls, x1, y1, x2, y2 });

describe('view', () => {
  it('fits the image at 92% of the stage, centred (like today)', () => {
    expect(fitView(200, 100, 1000, 1000)).toEqual({ scale: expect.closeTo(4.6), ox: expect.closeTo(40), oy: expect.closeTo(270) });
  });

  it('converts between image fractions and stage pixels', () => {
    const view = { scale: 2, ox: 10, oy: 20 };
    expect(toStage(view, IMG, [0.5, 0.5])).toEqual([210, 120]);
    expect(toImage(view, IMG, [210, 120])).toEqual([0.5, 0.5]);
  });

  it('zooms around the pointer so the point under it stays put', () => {
    const view = { scale: 2, ox: 10, oy: 20 };
    const zoomed = zoomAt(view, 1.15, [210, 120]);
    expect(zoomed.scale).toBeCloseTo(2.3);
    expect(toImage(zoomed, IMG, [210, 120])).toEqual([expect.closeTo(0.5), expect.closeTo(0.5)]);
  });
});

describe('hitBox (today: the selected box wins, then the smallest)', () => {
  const boxes = [box(0, 0, 1, 1), box(0.4, 0.4, 0.6, 0.6), box(0.45, 0.45, 0.55, 0.55)];

  it('picks the smallest box under the point', () => {
    expect(hitBox(boxes, [0.5, 0.5], {})).toBe(2);
  });

  it('prefers the selected box', () => {
    expect(hitBox(boxes, [0.5, 0.5], { selected: 0 })).toBe(0);
  });

  it('skips hidden boxes and, in solo mode, every box but the selected one', () => {
    expect(hitBox(boxes, [0.5, 0.5], { hidden: new Set([2]) })).toBe(1);
    expect(hitBox(boxes, [0.5, 0.5], { solo: true, selected: 1 })).toBe(1);
    expect(hitBox(boxes, [0.1, 0.1], { solo: true, selected: 1 })).toBe(-1);
  });

  it('returns -1 on empty space', () => {
    expect(hitBox([box(0, 0, 0.1, 0.1)], [0.5, 0.5], {})).toBe(-1);
  });
});

describe('hitCorner', () => {
  const view = { scale: 1, ox: 0, oy: 0 };
  it('finds a corner within 9 px', () => {
    const b = box(0.1, 0.1, 0.5, 0.5); // stage corners (20,10) (100,10) (20,50) (100,50)
    expect(hitCorner(b, [25, 15], view, IMG)).toBe('tl');
    expect(hitCorner(b, [100, 50], view, IMG)).toBe('br');
    expect(hitCorner(b, [60, 30], view, IMG)).toBeNull();
  });
});

describe('editing', () => {
  it('a new box needs more than 0.004 each way and is clamped and ordered', () => {
    expect(newBox([0.5, 0.5], [0.502, 0.9], 3)).toBeNull();
    expect(newBox([0.6, 0.8], [0.2, 0.4], 3)).toEqual(box(0.2, 0.4, 0.6, 0.8, 3));
  });

  it('moving keeps the box inside the image and its size', () => {
    const moved = moveBox(box(0.1, 0.1, 0.3, 0.3), 0.8, -0.5);
    expect(moved).toEqual(box(expect.closeTo(0.8), expect.closeTo(0), expect.closeTo(1), expect.closeTo(0.2)));
  });

  it('resizing moves only the grabbed corner, clamped to the image', () => {
    expect(resizeBox(box(0.1, 0.1, 0.5, 0.5), 'br', [1.2, 0.7])).toEqual(box(0.1, 0.1, 1, 0.7));
    expect(resizeBox(box(0.1, 0.1, 0.5, 0.5), 'tl', [0.3, -0.1])).toEqual(box(0.3, 0, 0.5, 0.5));
  });

  it('normalizing puts the corners back in order after a resize past the other side', () => {
    expect(normalizeBox(box(0.6, 0.7, 0.2, 0.3, 1))).toEqual(box(0.2, 0.3, 0.6, 0.7, 1));
  });
});

describe('hitBox with outlines', () => {
  const outlined = { cls: 0, x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5, points: [[0.1, 0.1], [0.5, 0.1], [0.3, 0.5]] };

  it('clicking the empty corner of an outlined object\'s box misses it', () => {
    expect(hitBox([outlined], [0.12, 0.45], {})).toBe(-1);
    expect(hitBox([outlined], [0.3, 0.2], {})).toBe(0);
  });
});
