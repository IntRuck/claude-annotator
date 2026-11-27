/*
 * The Outline tool (O): each click drops a dot; clicking the first dot (3+ dots) or Enter closes the outline.
 * The outline in progress (`draft`, dots in image fractions, or null) lives in the Editor; closing it is one undo
 * step. With an object selected, closing gives that object the outline; otherwise it's a new object.
 */
import { toImage } from './geometry';
import { dotDrag, startDrag } from './interaction';
import { MIN_DOTS, hitDot, withOutline } from './outline';

const clampPoint = ([x, y]) => [Math.max(0, Math.min(1, x)), Math.max(0, Math.min(1, y))];

/** The actions that finish an outline, or [] when it has fewer than MIN_DOTS dots. */
export function closeDraft(draft, ctx) {
  if (!draft || draft.length < MIN_DOTS) return [];
  const { boxes, selected, currentClass } = ctx;
  if (boxes[selected]) return [{ type: 'update', index: selected, box: withOutline(boxes[selected], draft) }];
  return [{ type: 'add', box: withOutline({ cls: currentClass, source: 'human' }, draft) }];
}

/** The outline without its last dot; null once no dot is left. */
export const removeLastDot = (draft) => (draft?.length > 1 ? draft.slice(0, -1) : null);

/** A mouse press in the Outline tool → { draft, drag, actions }. */
export function outlineDown(ctx, draft, point, button) {
  if (button === 1 || button === 2 || ctx.spaceHeld || !ctx.showAnnotations) {
    return { draft, ...startDrag(ctx, point, button) }; // pan, keeping the outline in progress
  }
  const onDot = draft ? null : dotDrag(ctx, point);
  if (onDot) return { draft, drag: onDot, actions: [] };
  if (!ctx.hasClasses) return { draft, drag: null, actions: [{ type: 'needClasses' }] };

  const { view, img } = ctx;
  if (draft?.length >= MIN_DOTS && hitDot(draft, point, view, img) === 0) {
    return { draft: null, drag: null, actions: closeDraft(draft, ctx) };
  }
  if (draft && hitDot([draft.at(-1)], point, view, img) === 0) return { draft, drag: null, actions: [] };
  return { draft: [...(draft ?? []), clampPoint(toImage(view, img, point))], drag: null, actions: [] };
}
