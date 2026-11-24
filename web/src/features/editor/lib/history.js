/*
 * Editor state with undo/redo (up to 200 steps per image, like today).
 * A drag sends `preview` actions (no history) and one `commit` at the end, so it's a single undo step.
 */
export const MAX_UNDO = 200;

export const initialEditor = { boxes: [], selected: -1, past: [], future: [], dirty: false, dragStart: null };

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

function change(state, boxes, extra = {}) {
  return {
    ...state,
    past: [...state.past, state.boxes].slice(-MAX_UNDO),
    future: [],
    boxes,
    dirty: true,
    ...extra,
  };
}

export function editorReducer(state, action) {
  switch (action.type) {
    case 'load':
      return { ...initialEditor, boxes: action.boxes };
    case 'select':
      return { ...state, selected: action.index };
    case 'add':
      return change(state, [...state.boxes, action.box], { selected: state.boxes.length });
    case 'setClass': {
      const current = state.boxes[state.selected];
      if (!current || current.cls === action.cls) return state;
      return change(state, state.boxes.map((b, i) => (i === state.selected ? { ...b, cls: action.cls, source: 'human' } : b)));
    }
    case 'remove':
      if (state.selected < 0) return state;
      return change(state, state.boxes.filter((_, i) => i !== state.selected), { selected: -1 });
    case 'preview':
      return {
        ...state,
        dragStart: state.dragStart ?? state.boxes,
        boxes: state.boxes.map((b, i) => (i === action.index ? action.box : b)),
      };
    case 'commit': {
      const before = state.dragStart;
      if (!before) return state;
      if (same(before, state.boxes)) return { ...state, dragStart: null };
      // Boxes the drag changed are now the person's boxes.
      const boxes = state.boxes.map((b, i) => (same(b, before[i]) ? b : { ...b, source: 'human' }));
      return { ...change({ ...state, boxes: before }, boxes), dragStart: null };
    }
    case 'undo': {
      if (!state.past.length) return state;
      return {
        ...state, boxes: state.past.at(-1), past: state.past.slice(0, -1), future: [state.boxes, ...state.future],
        selected: -1, dirty: true,
      };
    }
    case 'redo': {
      if (!state.future.length) return state;
      return {
        ...state, boxes: state.future[0], future: state.future.slice(1), past: [...state.past, state.boxes],
        selected: -1, dirty: true,
      };
    }
    case 'saved':
      return { ...state, boxes: action.boxes, dirty: false, selected: state.selected < action.boxes.length ? state.selected : -1 };
    default:
      return state;
  }
}
