/*
 * Outlines: an object's dots joined by straight lines, closing back to the first ([[x, y], ...] in image fractions).
 * An outlined object's box (x1..y2) is always the smallest box around its dots.
 */
import { CORNER_GRAB_PX, insideOutline, moveBox, toStage } from './geometry';

export { insideOutline };

export const MIN_DOTS = 3;

export function boundsOf(points) {
  const xs = points.map(([x]) => x);
  const ys = points.map(([, y]) => y);
  return { x1: Math.min(...xs), y1: Math.min(...ys), x2: Math.max(...xs), y2: Math.max(...ys) };
}

/** The object with this outline; its box follows the dots. */
export function withOutline(box, points) {
  return { ...box, points, ...boundsOf(points) };
}

/** The same object as a plain box (same corners). */
export function withoutOutline(box) {
  const plain = { ...box };
  delete plain.points;
  return plain;
}

export const outlineCount = (boxes) => boxes.filter((b) => b.points).length;

/** Index of the dot within `tol` stage pixels of a stage point, or -1. */
export function hitDot(points, [px, py], view, img, tol = CORNER_GRAB_PX) {
  return points.findIndex((dot) => {
    const [sx, sy] = toStage(view, img, dot);
    return Math.abs(sx - px) < tol && Math.abs(sy - py) < tol;
  });
}

function distanceToSegment([px, py], [ax, ay], [bx, by]) {
  const dx = bx - ax;
  const dy = by - ay;
  const lengthSq = dx * dx + dy * dy;
  const t = lengthSq ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lengthSq)) : 0;
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

/** Index i of the line from dot i to dot i+1 (the last closes back to dot 0) within `tol` stage pixels, or -1. */
export function hitEdge(points, point, view, img, tol = CORNER_GRAB_PX) {
  const stage = points.map((dot) => toStage(view, img, dot));
  return stage.findIndex((a, i) => distanceToSegment(point, a, stage[(i + 1) % stage.length]) < tol);
}

/** A new dot after dot `edge`, at an image point. */
export function insertDot(points, edge, dot) {
  return [...points.slice(0, edge + 1), dot, ...points.slice(edge + 1)];
}

/** The outline without dot i, or null when that would leave fewer than MIN_DOTS. */
export function removeDot(points, i) {
  return points.length > MIN_DOTS ? points.filter((_, j) => j !== i) : null;
}

/** Move the whole object, stopping at the image edges as a whole (like moveBox), so it keeps its shape. */
export function moveOutline(box, dx, dy) {
  const moved = moveBox(box, dx, dy);
  const mx = moved.x1 - box.x1;
  const my = moved.y1 - box.y1;
  return { ...moved, points: box.points.map(([x, y]) => [x + mx, y + my]) };
}
