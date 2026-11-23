/** Id of the image `delta` steps from `currentId` in `list`, clamped to the ends (today's A/D behaviour). */
export function stepFrom(list, currentId, delta) {
  if (list.length === 0) return null;
  const i = list.findIndex((item) => item.id === currentId);
  const next = i < 0 ? 0 : Math.max(0, Math.min(list.length - 1, i + delta));
  return list[next].id;
}

/** 1-based position of `currentId` in `list`, or null. */
export function positionOf(list, currentId) {
  const i = list.findIndex((item) => item.id === currentId);
  return i < 0 ? null : i + 1;
}
