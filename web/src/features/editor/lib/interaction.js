/*
 * Pointer interaction on the canvas, as plain functions (same modes as today's index.html):
 * pan, resize a corner of the selected box, move a box, or draw a new box.
 * Each returns editor actions (see history.js) for the component to dispatch.
 */
import { hitBox, hitCorner, moveBox, newBox, normalizeBox, resizeBox, toImage } from './geometry';

const clampPoint = ([x, y]) => [Math.max(0, Math.min(1, x)), Math.max(0, Math.min(1, y))];

export function startDrag(ctx, point, button) {
  const { boxes, selected, hidden, solo, view, img } = ctx;
  if (button === 1 || button === 2 || ctx.tool === 'pan' || ctx.spaceHeld || !ctx.showAnnotations) {
    return { drag: { mode: 'pan', p: point, ox: view.ox, oy: view.oy }, actions: [] };
  }
  const selectedBox = boxes[selected];
  const corner = selectedBox && !hidden.has(selected) ? hitCorner(selectedBox, point, view, img) : null;
  if (corner) return { drag: { mode: 'resize', corner, index: selected }, actions: [] };

  const n = toImage(view, img, point);
  const hit = hitBox(boxes, n, { selected, hidden, solo });
  if (hit >= 0) {
    return { drag: { mode: 'move', index: hit, start: n, orig: boxes[hit] }, actions: [{ type: 'select', index: hit }] };
  }
  if (!ctx.hasClasses) return { drag: null, actions: [{ type: 'needClasses' }] };
  return { drag: { mode: 'new', a: n, b: n }, actions: [{ type: 'select', index: -1 }] };
}

export function moveDrag(drag, ctx, point) {
  if (!drag) return { drag, actions: [] };
  if (drag.mode === 'pan') {
    return { drag, actions: [], view: { ...ctx.view, ox: drag.ox + point[0] - drag.p[0], oy: drag.oy + point[1] - drag.p[1] } };
  }
  const n = clampPoint(toImage(ctx.view, ctx.img, point));
  if (drag.mode === 'new') return { drag: { ...drag, b: n }, actions: [] };
  const box = drag.mode === 'move'
    ? moveBox(drag.orig, n[0] - drag.start[0], n[1] - drag.start[1])
    : resizeBox(ctx.boxes[drag.index], drag.corner, n);
  return { drag, actions: [{ type: 'preview', index: drag.index, box }] };
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
