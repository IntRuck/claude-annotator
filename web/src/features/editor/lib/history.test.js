import { describe, expect, it } from 'vitest';
import { editorReducer, initialEditor } from './history';

const b = (cls, x1 = 0.1) => ({ cls, x1, y1: 0.1, x2: x1 + 0.2, y2: 0.3, source: 'human' });
const run = (actions, start = initialEditor) => actions.reduce(editorReducer, start);

describe('editorReducer', () => {
  it('load sets the boxes and clears history and unsaved changes', () => {
    const s = run([{ type: 'add', box: b(0) }, { type: 'load', boxes: [b(1)] }]);
    expect(s).toMatchObject({ boxes: [b(1)], selected: -1, past: [], future: [], dirty: false });
  });

  it('add selects the new box and can be undone and redone', () => {
    let s = run([{ type: 'load', boxes: [] }, { type: 'add', box: b(0) }]);
    expect(s).toMatchObject({ boxes: [b(0)], selected: 0, dirty: true });
    s = editorReducer(s, { type: 'undo' });
    expect(s.boxes).toEqual([]);
    s = editorReducer(s, { type: 'redo' });
    expect(s.boxes).toEqual([b(0)]);
  });

  it('setClass changes the selected box (one undo step), and does nothing with no selection', () => {
    let s = run([{ type: 'load', boxes: [b(0)] }, { type: 'select', index: 0 }, { type: 'setClass', cls: 2 }]);
    expect(s.boxes[0].cls).toBe(2);
    expect(editorReducer(s, { type: 'undo' }).boxes[0].cls).toBe(0);
    const none = run([{ type: 'load', boxes: [b(0)] }, { type: 'setClass', cls: 2 }]);
    expect(none.boxes[0].cls).toBe(0);
    expect(none.dirty).toBe(false);
  });

  it('an edited box becomes a human box', () => {
    const s = run([{ type: 'load', boxes: [{ ...b(0), source: 'ai' }] }, { type: 'select', index: 0 }, { type: 'setClass', cls: 1 }]);
    expect(s.boxes[0].source).toBe('human');
  });

  it('remove deletes the selected box', () => {
    const s = run([{ type: 'load', boxes: [b(0), b(1)] }, { type: 'select', index: 0 }, { type: 'remove' }]);
    expect(s.boxes).toEqual([b(1)]);
    expect(s.selected).toBe(-1);
  });

  it('a drag previews without history, then commit makes one undo step', () => {
    let s = run([{ type: 'load', boxes: [b(0)] }, { type: 'select', index: 0 }]);
    s = run([{ type: 'preview', index: 0, box: b(0, 0.2) }, { type: 'preview', index: 0, box: b(0, 0.3) }], s);
    expect(s.past).toEqual([]);
    s = editorReducer(s, { type: 'commit' });
    expect(s.boxes[0].x1).toBe(0.3);
    expect(editorReducer(s, { type: 'undo' }).boxes[0].x1).toBe(0.1);
  });

  it('a commit with no real change adds no undo step', () => {
    const s = run([{ type: 'load', boxes: [b(0)] }, { type: 'preview', index: 0, box: b(0) }, { type: 'commit' }]);
    expect(s.past).toEqual([]);
  });

  it('keeps at most 200 undo steps', () => {
    let s = run([{ type: 'load', boxes: [] }]);
    for (let i = 0; i < 205; i += 1) s = editorReducer(s, { type: 'add', box: b(0, i / 1000) });
    expect(s.past).toHaveLength(200);
  });

  it('a new change clears redo', () => {
    const s = run([{ type: 'load', boxes: [] }, { type: 'add', box: b(0) }, { type: 'undo' }, { type: 'add', box: b(1) }]);
    expect(s.future).toEqual([]);
  });

  it('saved replaces the boxes with the server copy and clears unsaved changes', () => {
    const s = run([{ type: 'load', boxes: [] }, { type: 'add', box: b(0) }, { type: 'saved', boxes: [b(0)] }]);
    expect(s.dirty).toBe(false);
    expect(s.boxes).toEqual([b(0)]);
  });
});

describe('outlines in the editor state', () => {
  const outlined = { ...b(0), points: [[0.1, 0.1], [0.3, 0.1], [0.2, 0.3]] };

  it('update replaces one object in one undo step and marks it human', () => {
    let s = run([{ type: 'load', boxes: [b(0), { ...b(1, 0.5), source: 'ai' }] }, { type: 'select', index: 1 }]);
    s = editorReducer(s, { type: 'update', index: 1, box: { ...outlined, cls: 1, source: 'ai' } });
    expect(s.boxes[1]).toEqual({ ...outlined, cls: 1, source: 'human' });
    expect(s).toMatchObject({ selected: 1, dirty: true });
    expect(editorReducer(s, { type: 'undo' }).boxes[1]).toEqual({ ...b(1, 0.5), source: 'ai' });
  });

  it('setClass keeps the outline', () => {
    const s = run([{ type: 'load', boxes: [outlined] }, { type: 'select', index: 0 }, { type: 'setClass', cls: 3 }]);
    expect(s.boxes[0]).toEqual({ ...outlined, cls: 3 });
  });
});
