/*
 * Pointer interaction on the canvas, as plain functions (same modes as today's index.html):
 * pan, resize a corner of the selected box, move a box, or draw a new box; for outlines also drag one dot of the
 * selected outline, and double-click to add or remove a dot.
 * Each returns editor actions (see history.js) for the component to dispatch.
 */
import { hitBox, hitCorner, moveBox, newBox, normalizeBox, resizeBox, toImage } from './geometry';
import { hitDot, hitEdge, insertDot, moveOutline, removeDot, withOutline } from './outline';

const clampPoint = ([x, y]) => [Math.max(0, Math.min(1, x)), Math.max(0, Math.min(1, y))];

/** The selected object when it's visible and has an outline, else null. */
function selectedOutline({ boxes, selected, hidden }) {
  const box = boxes[selected];
  return box?.points && !hidden.has(selected) ? box : null;
}

/** A drag of one dot of the selected outline when the point is on one, else null. */
export function dotDrag(ctx, point) {
  const outlined = selectedOutline(ctx);
  const dot = outlined ? hitDot(outlined.points, point, ctx.view, ctx.img) : -1;
  return dot >= 0 ? { mode: 'dot', index: ctx.selected, dot } : null;
}

export function startDrag(ctx, point, button) {
  const { boxes, selected, hidden, solo, view, img } = ctx;
  if (button === 1 || button === 2 || ctx.tool === 'pan' || ctx.spaceHeld || !ctx.showAnnotations) {
    return { drag: { mode: 'pan', p: point, ox: view.ox, oy: view.oy }, actions: [] };
  }
  const onDot = dotDrag(ctx, point);
  if (onDot) return { drag: onDot, actions: [] };

  const n = toImage(view, img, point);
  // On (or just outside) a line of the selected outline: keep it selected, so a double-click there can add a dot.
  const outlined = selectedOutline(ctx);
  if (outlined && hitEdge(outlined.points, point, view, img) >= 0) {
    return { drag: { mode: 'move', index: selected, start: n, orig: outlined }, actions: [] };
  }

  const selectedBox = boxes[selected];
  // Outlined objects are reshaped by their dots, so their box corners can't be dragged.
  const corner = selectedBox && !selectedBox.points && !hidden.has(selected) ? hitCorner(selectedBox, point, view, img) : null;
  if (corner) return { drag: { mode: 'resize', corner, index: selected }, actions: [] };

  const hit = hitBox(boxes, n, { selected, hidden, solo });
  if (hit >= 0) {
    return { drag: { mode: 'move', index: hit, start: n, orig: boxes[hit] }, actions: [{ type: 'select', index: hit }] };
  }
  if (!ctx.hasClasses) return { drag: null, actions: [{ type: 'needClasses' }] };
  return { drag: { mode: 'new', a: n, b: n }, actions: [{ type: 'select', index: -1 }] };
}

function dragged(drag, ctx, n) {
  if (drag.mode === 'dot') {
    const box = ctx.boxes[drag.index];
    return withOutline(box, box.points.map((p, i) => (i === drag.dot ? n : p)));
  }
  if (drag.mode === 'move') {
    const move = drag.orig.points ? moveOutline : moveBox;
    return move(drag.orig, n[0] - drag.start[0], n[1] - drag.start[1]);
  }
  return resizeBox(ctx.boxes[drag.index], drag.corner, n);
}

export function moveDrag(drag, ctx, point) {
  if (!drag) return { drag, actions: [] };
  if (drag.mode === 'pan') {
    return { drag, actions: [], view: { ...ctx.view, ox: drag.ox + point[0] - drag.p[0], oy: drag.oy + point[1] - drag.p[1] } };
  }
  const n = clampPoint(toImage(ctx.view, ctx.img, point));
  if (drag.mode === 'new') return { drag: { ...drag, b: n }, actions: [] };
  return { drag, actions: [{ type: 'preview', index: drag.index, box: dragged(drag, ctx, n) }] };
}

export function endDrag(drag, ctx) {
  if (!drag || drag.mode === 'pan') return [];
  if (drag.mode === 'new') {
    const box = newBox(drag.a, drag.b, ctx.currentClass);
    return box ? [{ type: 'add', box: { ...box, source: 'human' } }] : [];
  }
  if (drag.mode === 'resize') {
    const current = ctx.boxes[drag.index];
    const ordered = normalizeBox(current);
    const crossed = ordered.x1 !== current.x1 || ordered.y1 !== current.y1;
    return crossed ? [{ type: 'preview', index: drag.index, box: ordered }, { type: 'commit' }] : [{ type: 'commit' }];
  }
  return [{ type: 'commit' }];
}

/**
 * Double-click with the Box tool on the selected outline: on a dot removes it (an outline keeps at least 3),
 * on a line adds a dot there. (In the Outline tool every click drops a dot, so this is the Box tool's.)
 */
export function doubleClick(ctx, point) {
  const outlined = ctx.tool === 'box' ? selectedOutline(ctx) : null;
  if (!outlined) return [];
  const { view, img, selected: index } = ctx;
  const dot = hitDot(outlined.points, point, view, img);
  if (dot >= 0) {
    const points = removeDot(outlined.points, dot);
    return points ? [{ type: 'update', index, box: withOutline(outlined, points) }] : [];
  }
  const edge = hitEdge(outlined.points, point, view, img);
  if (edge < 0) return [];
  const points = insertDot(outlined.points, edge, clampPoint(toImage(view, img, point)));
  return [{ type: 'update', index, box: withOutline(outlined, points) }];
}
