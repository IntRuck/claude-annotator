/*
 * Editor geometry. Boxes are in image fractions (0-1); the view maps them to stage pixels:
 * stage = offset + fraction * imageSize * scale. Numbers match today's index.html.
 */
export const FIT_MARGIN = 0.92;
export const MIN_NEW_SIDE = 0.004;
export const CORNER_GRAB_PX = 9;

const clamp01 = (v) => Math.max(0, Math.min(1, v));

export function fitView(iw, ih, sw, sh) {
  const scale = Math.min(sw / iw, sh / ih) * FIT_MARGIN;
  return { scale, ox: (sw - iw * scale) / 2, oy: (sh - ih * scale) / 2 };
}

export function toStage(view, { iw, ih }, [x, y]) {
  return [view.ox + x * iw * view.scale, view.oy + y * ih * view.scale];
}

export function toImage(view, { iw, ih }, [px, py]) {
  return [(px - view.ox) / (iw * view.scale), (py - view.oy) / (ih * view.scale)];
}

/** Zoom by `k` around a stage point, keeping the image point under it in place. */
export function zoomAt(view, k, [cx, cy]) {
  return { scale: view.scale * k, ox: cx - (cx - view.ox) * k, oy: cy - (cy - view.oy) * k };
}

/** Is an image point inside an outline ([[x, y], ...])? Ray casting: count the lines a ray to the right crosses. */
export function insideOutline(points, [nx, ny]) {
  let inside = false;
  points.forEach(([ax, ay], i) => {
    const [bx, by] = points[(i + 1) % points.length];
    if ((ay > ny) !== (by > ny) && nx < ax + ((ny - ay) * (bx - ax)) / (by - ay)) inside = !inside;
  });
  return inside;
}

/**
 * Index of the box under an image point: the selected box first, else the smallest. -1 if none.
 * An outlined object is hit only inside its outline (its box size still decides "smallest").
 */
export function hitBox(boxes, [nx, ny], { selected = -1, hidden = new Set(), solo = false } = {}) {
  let best = -1;
  let bestArea = Infinity;
  boxes.forEach((b, i) => {
    if (hidden.has(i) || (solo && selected >= 0 && i !== selected)) return;
    if (nx < b.x1 || nx > b.x2 || ny < b.y1 || ny > b.y2) return;
    if (b.points && !insideOutline(b.points, [nx, ny])) return;
    const area = i === selected ? -1 : (b.x2 - b.x1) * (b.y2 - b.y1);
    if (area < bestArea) {
      best = i;
      bestArea = area;
    }
  });
  return best;
}

/** Which corner of `box` is within CORNER_GRAB_PX of a stage point: 'tl' | 'tr' | 'bl' | 'br' | null. */
export function hitCorner(box, point, view, img, tol = CORNER_GRAB_PX) {
  const corners = { tl: [box.x1, box.y1], tr: [box.x2, box.y1], bl: [box.x1, box.y2], br: [box.x2, box.y2] };
  for (const [name, corner] of Object.entries(corners)) {
    const [cx, cy] = toStage(view, img, corner);
    if (Math.abs(cx - point[0]) < tol && Math.abs(cy - point[1]) < tol) return name;
  }
  return null;
}

/** A new box between two image points, or null when it's too small (a click, not a drag). */
export function newBox(a, b, cls) {
  if (Math.abs(a[0] - b[0]) <= MIN_NEW_SIDE || Math.abs(a[1] - b[1]) <= MIN_NEW_SIDE) return null;
  return {
    cls,
    x1: clamp01(Math.min(a[0], b[0])), y1: clamp01(Math.min(a[1], b[1])),
    x2: clamp01(Math.max(a[0], b[0])), y2: clamp01(Math.max(a[1], b[1])),
  };
}

/** Move a box by (dx, dy), stopping at the image edges so it keeps its size. */
export function moveBox(orig, dx, dy) {
  const mx = Math.max(-orig.x1, Math.min(1 - orig.x2, dx));
  const my = Math.max(-orig.y1, Math.min(1 - orig.y2, dy));
  return { ...orig, x1: orig.x1 + mx, y1: orig.y1 + my, x2: orig.x2 + mx, y2: orig.y2 + my };
}

/** Move one corner to an image point (clamped to the image). Corners may cross; normalizeBox fixes that. */
export function resizeBox(box, corner, [nx, ny]) {
  const x = clamp01(nx);
  const y = clamp01(ny);
  return {
    ...box,
    ...(corner.includes('l') ? { x1: x } : { x2: x }),
    ...(corner.includes('t') ? { y1: y } : { y2: y }),
  };
}

export function normalizeBox(b) {
  return { ...b, x1: Math.min(b.x1, b.x2), x2: Math.max(b.x1, b.x2), y1: Math.min(b.y1, b.y2), y2: Math.max(b.y1, b.y2) };
}
