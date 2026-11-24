import { describe, expect, it } from 'vitest';
import { endDrag, moveDrag, startDrag } from './interaction';

// Image 200x100 drawn at scale 1 from the stage origin: image fraction (x, y) = stage (200x, 100y).
const ctx = (extra = {}) => ({
  boxes: [{ cls: 0, x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5, source: 'ai' }],
  selected: -1, hidden: new Set(), solo: false, view: { scale: 1, ox: 0, oy: 0 }, img: { iw: 200, ih: 100 },
  tool: 'box', spaceHeld: false, currentClass: 2, hasClasses: true, showAnnotations: true, ...extra,
});

describe('pointer interaction (same modes as today: pan, resize, move, new box)', () => {
  it('drag on empty space draws a new box with the current class', () => {
    const start = startDrag(ctx(), [140, 70], 0);
    expect(start.actions).toEqual([{ type: 'select', index: -1 }]);
    const moved = moveDrag(start.drag, ctx(), [180, 90]);
    expect(endDrag(moved.drag, ctx())).toEqual([{ type: 'add', box: { cls: 2, x1: 0.7, y1: 0.7, x2: 0.9, y2: 0.9, source: 'human' } }]);
  });

  it('a click without dragging draws nothing', () => {
    const start = startDrag(ctx(), [140, 70], 0);
    expect(endDrag(start.drag, ctx())).toEqual([]);
  });

  it('drawing needs a class first', () => {
    expect(startDrag(ctx({ hasClasses: false }), [140, 70], 0)).toEqual({ drag: null, actions: [{ type: 'needClasses' }] });
  });

  it('pressing on a box selects it and dragging moves it (inside the image), then commits', () => {
    const start = startDrag(ctx(), [60, 30], 0);
    expect(start.actions).toEqual([{ type: 'select', index: 0 }]);
    const moved = moveDrag(start.drag, ctx({ selected: 0 }), [80, 40]);
    expect(moved.actions).toEqual([{ type: 'preview', index: 0, box: expect.objectContaining({ x1: expect.closeTo(0.2), y1: expect.closeTo(0.2), x2: expect.closeTo(0.6), y2: expect.closeTo(0.6) }) }]);
    expect(endDrag(moved.drag, ctx({ selected: 0 }))).toEqual([{ type: 'commit' }]);
  });

  it('dragging a corner of the selected box resizes it and puts the corners in order at the end', () => {
    const c = ctx({ selected: 0 });
    const start = startDrag(c, [100, 50], 0); // bottom-right corner
    expect(start.drag.mode).toBe('resize');
    const moved = moveDrag(start.drag, c, [10, 5]); // past the top-left corner
    expect(moved.actions[0].box).toMatchObject({ x1: 0.1, y1: 0.1, x2: 0.05, y2: 0.05 });
    const after = { ...c, boxes: [moved.actions[0].box] };
    expect(endDrag(moved.drag, after)).toEqual([
      { type: 'preview', index: 0, box: expect.objectContaining({ x1: 0.05, y1: 0.05, x2: 0.1, y2: 0.1 }) },
      { type: 'commit' },
    ]);
  });

  it.each([
    ['right button', ctx(), 2],
    ['middle button', ctx(), 1],
    ['pan tool', ctx({ tool: 'pan' }), 0],
    ['space held', ctx({ spaceHeld: true }), 0],
    ['annotations hidden', ctx({ showAnnotations: false }), 0],
  ])('%s pans the view', (_, c, button) => {
    const start = startDrag(c, [60, 30], button);
    expect(start.drag.mode).toBe('pan');
    expect(moveDrag(start.drag, c, [90, 50]).view).toEqual({ scale: 1, ox: 30, oy: 20 });
    expect(endDrag(start.drag, c)).toEqual([]);
  });
});
