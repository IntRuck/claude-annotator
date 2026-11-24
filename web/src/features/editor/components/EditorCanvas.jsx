import { useEffect, useEffectEvent, useRef, useState } from 'react';
import { Group, Layer, Rect, Stage, Text } from 'react-konva';
import { classColor } from '@/features/classes';
import { fitView, toStage, zoomAt } from '../lib/geometry';
import '../styles/editor.css';

const ZOOM_STEP = 1.15;
const HANDLE = 4;

function alpha(color, a) {
  return color.replace(')', ` / ${a})`);
}

/**
 * Draws the image (an <img>, so brightness/contrast only touch the photo) and the boxes on a Konva stage.
 * Pointer events are reported as stage points; the editing logic lives in lib/interaction.js.
 */
export default function EditorCanvas({
  imageUrl, img, boxes, classes, selected, hidden, solo, display, view, draft, fitToken = 0,
  onView, onPointerDown, onPointerMove, onPointerUp,
}) {
  const wrap = useRef(null);
  const [size, setSize] = useState({ w: 800, h: 600 });
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    const el = wrap.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width && height) setSize({ w: width, h: height });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Fit when the image or the space changes, or when F is pressed (fitToken).
  useEffect(() => {
    onView(fitView(img.iw, img.ih, size.w, size.h));
  }, [img.iw, img.ih, imageUrl, size.w, size.h, fitToken, onView]);

  const pointOf = (e) => {
    const r = wrap.current.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  };

  // Wheel zoom around the pointer (a native listener, so the page doesn't scroll).
  const onWheel = useEffectEvent((e) => {
    e.preventDefault();
    onView(zoomAt(view, e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP, pointOf(e)));
  });
  useEffect(() => {
    const el = wrap.current;
    const listener = (e) => onWheel(e);
    el.addEventListener('wheel', listener, { passive: false });
    return () => el.removeEventListener('wheel', listener);
  }, []);

  // While dragging, follow the pointer anywhere on the page (like today).
  const onMove = useEffectEvent((e) => onPointerMove(pointOf(e)));
  const onUp = useEffectEvent(() => {
    setDragging(false);
    onPointerUp();
  });
  useEffect(() => {
    if (!dragging) return undefined;
    const move = (e) => onMove(e);
    const up = () => onUp();
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
    return () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
    };
  }, [dragging]);

  const down = (e) => {
    onPointerDown(pointOf(e), e.button);
    setDragging(true);
  };

  const nameOf = (cls) => classes.find((c) => c.index === cls)?.name ?? `ID ${cls}`;
  const visible = display.showAnnotations
    ? boxes.map((b, i) => ({ b, i })).filter(({ i }) => !hidden.has(i) && !(solo && selected >= 0 && i !== selected))
    : [];

  return (
    <div className="editor-canvas" ref={wrap} onMouseDown={down} onContextMenu={(e) => e.preventDefault()}>
      <img data-testid="stage-image" src={imageUrl} alt="" draggable={false} className="stage-photo"
           style={{
             width: img.iw, height: img.ih,
             transform: `translate(${view.ox}px, ${view.oy}px) scale(${view.scale})`,
             filter: `brightness(${display.brightness}) contrast(${display.contrast})`,
           }} />
      <Stage width={size.w} height={size.h} listening={false} className="stage-boxes">
        <Layer>
          {visible.map(({ b, i }) => {
            const [x1, y1] = toStage(view, img, [b.x1, b.y1]);
            const [x2, y2] = toStage(view, img, [b.x2, b.y2]);
            const color = classColor(b.cls);
            const isSelected = i === selected;
            return (
              // Box position is its identity while editing.
              <Group key={i}>
                <Rect name="box" x={x1} y={y1} width={x2 - x1} height={y2 - y1} stroke={color}
                      strokeWidth={isSelected ? 3.6 : 2}
                      fill={isSelected || display.fillBoxes ? alpha(color, isSelected ? 0.22 : 0.12) : undefined} />
                {display.showNames && (
                  <Group>
                    <Rect x={x1} y={y1 - 16} width={nameOf(b.cls).length * 6.5 + 8} height={16} fill={color} />
                    <Text x={x1 + 4} y={y1 - 13} text={nameOf(b.cls)} fontSize={11} fontStyle="600" fill="#fff" />
                  </Group>
                )}
                {isSelected && [[x1, y1], [x2, y1], [x1, y2], [x2, y2]].map(([hx, hy]) => (
                  <Rect key={`${hx},${hy}`} name="handle" x={hx - HANDLE} y={hy - HANDLE} width={HANDLE * 2} height={HANDLE * 2}
                        fill="#fff" stroke={color} strokeWidth={1} />
                ))}
              </Group>
            );
          })}
          {draft && (() => {
            const [x1, y1] = toStage(view, img, draft.a);
            const [x2, y2] = toStage(view, img, draft.b);
            return <Rect name="draft" x={x1} y={y1} width={x2 - x1} height={y2 - y1} stroke="#fff" dash={[6, 4]} strokeWidth={2} />;
          })()}
        </Layer>
      </Stage>
    </div>
  );
}
