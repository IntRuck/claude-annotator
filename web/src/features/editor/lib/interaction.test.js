import { describe, expect, it } from 'vitest';
import { doubleClick, endDrag, moveDrag, startDrag } from './interaction';
import { withOutline } from './outline';

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

describe('editing outlines', () => {
  // Dots at stage (20,10), (100,10), (60,50); its box is stage (20,10)-(100,50).
  const TRIANGLE = [[0.1, 0.1], [0.5, 0.1], [0.3, 0.5]];
  const outlined = withOutline({ cls: 0, source: 'ai' }, TRIANGLE);
  const octx = (extra = {}) => ctx({ boxes: [outlined], ...extra });

  it('dragging a dot of the selected outline moves only that dot', () => {
    const c = octx({ selected: 0 });
    const start = startDrag(c, [60, 50], 0);
    expect(start.drag).toMatchObject({ mode: 'dot', index: 0, dot: 2 });
    const moved = moveDrag(start.drag, c, [60, 80]);
    expect(moved.actions).toEqual([{ type: 'preview', index: 0, box: withOutline(outlined, [[0.1, 0.1], [0.5, 0.1], [0.3, 0.8]]) }]);
    expect(endDrag(moved.drag, c)).toEqual([{ type: 'commit' }]);
  });

  it('pressing just outside a line of the selected outline keeps it selected, so a double-click can add a dot', () => {
    const start = startDrag(octx({ selected: 0 }), [60, 6], 0); // 4 px above the top line, outside the triangle
    expect(start.drag.mode).toBe('move');
    expect(start.actions).toEqual([]);
  });

  it('an outlined object has no corner handles to resize', () => {
    expect(startDrag(octx({ selected: 0 }), [100, 50], 0).drag.mode).toBe('new'); // its box corner, outside the outline
  });

  it('moving an outlined object moves its dots', () => {
    const c = octx({ selected: 0 });
    const start = startDrag(c, [60, 25], 0);
    expect(start.drag.mode).toBe('move');
    const { box } = moveDrag(start.drag, c, [80, 35]).actions[0];
    expect(box.points).toEqual([[expect.closeTo(0.2), expect.closeTo(0.2)], [expect.closeTo(0.6), expect.closeTo(0.2)],
      [expect.closeTo(0.4), expect.closeTo(0.6)]]);
  });

  it('double-click on a line adds a dot there', () => {
    expect(doubleClick(octx({ selected: 0 }), [60, 10])).toEqual([
      { type: 'update', index: 0, box: withOutline(outlined, [[0.1, 0.1], [0.3, 0.1], [0.5, 0.1], [0.3, 0.5]]) },
    ]);
  });

  it('double-click on a dot removes it but never below 3', () => {
    const square = withOutline({ cls: 0 }, [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]);
    expect(doubleClick(ctx({ boxes: [square], selected: 0 }), [100, 50])).toEqual([
      { type: 'update', index: 0, box: withOutline(square, [[0.1, 0.1], [0.5, 0.1], [0.1, 0.5]]) },
    ]);
    expect(doubleClick(octx({ selected: 0 }), [60, 50])).toEqual([]);
  });

  it('double-click does nothing in the pan tool or on an unselected object', () => {
    expect(doubleClick(octx({ selected: 0, tool: 'pan' }), [60, 10])).toEqual([]);
    expect(doubleClick(octx(), [60, 10])).toEqual([]);
    expect(doubleClick(ctx({ selected: 0 }), [60, 10])).toEqual([]); // a plain box
  });
});
