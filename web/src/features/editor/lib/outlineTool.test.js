import { describe, expect, it } from 'vitest';
import { withOutline } from './outline';
import { closeDraft, outlineDown, removeLastDot } from './outlineTool';

// Image 200x100 drawn at scale 1 from the stage origin: image fraction (x, y) = stage (200x, 100y).
const ctx = (extra = {}) => ({
  boxes: [{ cls: 0, x1: 0.6, y1: 0.6, x2: 0.9, y2: 0.9, source: 'ai' }],
  selected: -1, hidden: new Set(), solo: false, view: { scale: 1, ox: 0, oy: 0 }, img: { iw: 200, ih: 100 },
  tool: 'outline', spaceHeld: false, currentClass: 2, hasClasses: true, showAnnotations: true, ...extra,
});
const TRIANGLE = [[0.1, 0.1], [0.5, 0.1], [0.3, 0.5]];

describe('the Outline tool', () => {
  it('each click drops a dot, even on top of another object', () => {
    const first = outlineDown(ctx(), null, [20, 10], 0);
    expect(first).toEqual({ draft: [[0.1, 0.1]], drag: null, actions: [] });
    expect(outlineDown(ctx(), first.draft, [150, 70], 0).draft).toEqual([[0.1, 0.1], [0.75, 0.7]]); // inside the box
  });

  it('a second click on the last dot adds nothing', () => {
    expect(outlineDown(ctx(), [[0.1, 0.1]], [21, 11], 0).draft).toEqual([[0.1, 0.1]]);
  });

  it('clicking the first dot with 3 or more dots closes it as a new object of the current class', () => {
    expect(outlineDown(ctx(), TRIANGLE, [21, 11], 0)).toEqual({
      draft: null, drag: null, actions: [{ type: 'add', box: withOutline({ cls: 2, source: 'human' }, TRIANGLE) }],
    });
  });

  it('fewer than 3 dots will not close', () => {
    expect(closeDraft([[0.1, 0.1], [0.5, 0.1]], ctx())).toEqual([]);
    expect(closeDraft(null, ctx())).toEqual([]);
  });

  it('closing with an object selected gives that object the outline', () => {
    expect(closeDraft(TRIANGLE, ctx({ selected: 0 }))).toEqual([
      { type: 'update', index: 0, box: withOutline(ctx().boxes[0], TRIANGLE) },
    ]);
  });

  it('removeLastDot takes off the last dot, and the last one ends the outline', () => {
    expect(removeLastDot([[0.1, 0.1], [0.5, 0.1]])).toEqual([[0.1, 0.1]]);
    expect(removeLastDot([[0.1, 0.1]])).toBeNull();
  });

  it('drawing needs a class first', () => {
    expect(outlineDown(ctx({ hasClasses: false }), null, [20, 10], 0)).toEqual({
      draft: null, drag: null, actions: [{ type: 'needClasses' }],
    });
  });

  it('the right button or Space pans and keeps the outline in progress', () => {
    const right = outlineDown(ctx(), [[0.1, 0.1]], [60, 30], 2);
    expect(right.drag.mode).toBe('pan');
    expect(right.draft).toEqual([[0.1, 0.1]]);
    expect(outlineDown(ctx({ spaceHeld: true }), null, [60, 30], 0).drag.mode).toBe('pan');
  });

  it('before drawing, a dot of the selected outline can be dragged', () => {
    const outlined = withOutline({ cls: 0 }, TRIANGLE);
    const down = outlineDown(ctx({ boxes: [outlined], selected: 0 }), null, [100, 10], 0);
    expect(down).toEqual({ draft: null, drag: { mode: 'dot', index: 0, dot: 1 }, actions: [] });
  });
});
