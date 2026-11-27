import { useEffect, useEffectEvent, useRef, useState } from 'react';
import { ErrorBanner } from '@/components/ui';
import { fitView, zoomAt } from '../lib/geometry';
import { doubleClick, endDrag, moveDrag, startDrag } from '../lib/interaction';
import { closeDraft, outlineDown, removeLastDot } from '../lib/outlineTool';
import { commandFor } from '../lib/shortcuts';
import EditorCanvas from './EditorCanvas';
import '../styles/editor.css';

const DEFAULT_DISPLAY = { brightness: 1, contrast: 1, showAnnotations: true, showNames: true, fillBoxes: false };
const KEYS = [
  ['A / D', 'Previous / next image'], ['R', 'Approve and go to next'], ['G', '🚩 Flag / unflag'], ['S', 'Save'],
  ['B / V', 'Box tool / pan tool'], ['O', 'Outline tool: click dots, Enter or the first dot closes'],
  ['Backspace (drawing)', 'Remove the last dot'], ['Double-click', 'Add a dot on a line / remove a dot'],
  ['Space (hold)', 'Pan while held'], ['1–9', 'Pick class (and change selected box)'],
  ['Del', 'Delete selected box'], ['Ctrl+Z / Y', 'Undo / redo'], ['H', 'Show only selected box'],
  ['L', 'Show / hide class names'], ['F', 'Fit image'], ['Wheel / right-drag', 'Zoom / pan'], ['Esc', 'Deselect, close popups'],
];

/**
 * The box editor for one image: canvas, tool rail, zoom bar, display options and keyboard shortcuts.
 * Box state and saving come from useEditor (passed in as `editor`).
 */
export default function Editor({
  editor, image, imageUrl, classes, currentClass, hidden, solo, setSolo, dialogOpen,
  onPickClass, onStep, onApprove, onToggleFlag, onNeedClasses,
}) {
  const { state, dispatch } = editor;
  const img = { iw: image.width, ih: image.height };
  const [view, setView] = useState(() => fitView(img.iw, img.ih, 800, 600));
  const [tool, setTool] = useState('box');
  const [spaceHeld, setSpaceHeld] = useState(false);
  const [display, setDisplay] = useState(DEFAULT_DISPLAY);
  const [pop, setPop] = useState(null);
  const [fitToken, setFitToken] = useState(0);
  const [draft, setDraft] = useState(null);
  const [outline, setOutline] = useState(null); // dots of the outline being drawn (Outline tool), or null
  const [hover, setHover] = useState(null);
  const drag = useRef(null);

  const ctx = {
    boxes: state.boxes, selected: state.selected, hidden, solo, view, img, tool, spaceHeld,
    currentClass, hasClasses: classes.length > 0, showAnnotations: display.showAnnotations,
  };
  const run = (actions) => actions.forEach((a) => (a.type === 'needClasses' ? onNeedClasses() : dispatch(a)));

  const onPointerDown = (point, button) => {
    setPop(null);
    if (tool === 'outline') {
      const down = outlineDown(ctx, outline, point, button);
      drag.current = down.drag;
      setOutline(down.draft);
      run(down.actions);
      return;
    }
    const started = startDrag(ctx, point, button);
    drag.current = started.drag;
    run(started.actions);
    if (started.drag?.mode === 'new') setDraft({ a: started.drag.a, b: started.drag.b });
  };
  const onPointerMove = (point) => {
    if (!drag.current) return;
    const moved = moveDrag(drag.current, ctx, point);
    drag.current = moved.drag;
    if (moved.view) setView(moved.view);
    run(moved.actions);
    if (moved.drag?.mode === 'new') setDraft({ a: moved.drag.a, b: moved.drag.b });
  };
  const onPointerUp = () => {
    run(endDrag(drag.current, ctx));
    drag.current = null;
    setDraft(null);
  };

  const chooseTool = (next) => {
    if (next !== tool) setOutline(null);
    setTool(next);
  };
  const closeOutline = () => {
    const actions = closeDraft(outline, ctx);
    if (!actions.length) return;
    run(actions);
    setOutline(null);
  };

  // While an outline is being drawn, Backspace / Ctrl+Z take off its last dot and Esc drops it.
  const commands = {
    undo: () => (outline ? setOutline(removeLastDot(outline)) : dispatch({ type: 'undo' })),
    redo: () => dispatch({ type: 'redo' }),
    delete: () => (outline ? setOutline(removeLastDot(outline)) : dispatch({ type: 'remove' })),
    save: () => editor.save('edited').catch(() => {}),
    approve: onApprove,
    flag: onToggleFlag,
    next: () => onStep(1),
    prev: () => onStep(-1),
    boxTool: () => chooseTool('box'),
    panTool: () => chooseTool('pan'),
    outlineTool: () => chooseTool('outline'),
    closeOutline,
    solo: () => setSolo(!solo),
    names: () => setDisplay((d) => ({ ...d, showNames: !d.showNames })),
    fit: () => setFitToken((t) => t + 1),
    deselect: () => {
      if (outline) { setOutline(null); return; }
      dispatch({ type: 'select', index: -1 });
      setPop(null);
    },
  };

  // Keyboard shortcuts (today's keys).
  const onKeyDown = useEffectEvent((e) => {
    const cmd = commandFor(e, { dialogOpen });
    if (!cmd) return;
    if (cmd === 'blur') { e.target.blur(); return; }
    if (cmd === 'panHold') { e.preventDefault(); setSpaceHeld(true); return; }
    if (typeof cmd === 'object') {
      if (cmd.pickClass < classes.length) onPickClass(cmd.pickClass);
      return;
    }
    if (['undo', 'redo', 'save'].includes(cmd)) e.preventDefault();
    if (cmd === 'closeOutline') {
      if (!outline) return; // Enter keeps pressing a focused button when no outline is being drawn
      e.preventDefault();
    }
    commands[cmd]();
  });
  useEffect(() => {
    const down = (e) => onKeyDown(e);
    const up = (e) => { if (e.key === ' ') setSpaceHeld(false); };
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); };
  }, []);

  // Warn before leaving the page with unsaved changes.
  useEffect(() => {
    if (!state.dirty) return undefined;
    const warn = (e) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [state.dirty]);

  const fitScale = fitView(img.iw, img.ih, 800, 600).scale;
  const zoomBy = (k) => setView((v) => zoomAt(v, k, [400, 300]));
  const togglePop = (name) => setPop((p) => (p === name ? null : name));

  return (
    <div className={`editor${tool === 'pan' || spaceHeld ? ' panning' : ''}`}>
      <EditorCanvas imageUrl={imageUrl} img={img} boxes={state.boxes} classes={classes} selected={state.selected}
                    hidden={hidden} solo={solo} display={display} view={view} draft={draft} fitToken={fitToken}
                    outlineDraft={outline ? { points: outline, hover } : null}
                    onView={setView} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
                    onHover={(p) => { if (outline) setHover(p); }} onDoubleClick={(p) => run(doubleClick(ctx, p))} />

      {image.flagged && <div className="float flag-banner">🚩 Flagged{image.flagReason ? `: ${image.flagReason}` : ''}</div>}
      {editor.conflict && (
        <div className="float conflict" role="alert">
          This image was changed since you opened it (by someone else or the AI).
          <button type="button" onClick={editor.reload}>Reload</button>
        </div>
      )}
      {editor.error && <div className="float conflict"><ErrorBanner error={editor.error} /></div>}

      <div className="float rail">
        <button type="button" title="Box tool: drag to draw (B)" aria-pressed={tool === 'box'} onClick={commands.boxTool}>▭</button>
        <button type="button" title="Outline tool: click round the object, Enter to close (O)" aria-pressed={tool === 'outline'}
                onClick={commands.outlineTool}>⬠</button>
        <button type="button" title="Pan tool (V, or hold Space)" aria-pressed={tool === 'pan'} onClick={commands.panTool}>✋</button>
        <button type="button" title="Undo (Ctrl+Z)" onClick={commands.undo}>↶</button>
        <button type="button" title="Redo (Ctrl+Y)" onClick={commands.redo}>↷</button>
        <button type="button" title="Show only the selected box (H)" aria-pressed={solo} onClick={commands.solo}>◎</button>
        <button type="button" title="Delete selected box (Del)" onClick={commands.delete}>🗑</button>
      </div>

      <div className="float zoombar">
        <button type="button" title="Zoom out" onClick={() => zoomBy(1 / 1.25)}>−</button>
        <span className="pct">{Math.round((100 * view.scale) / fitScale)}%</span>
        <button type="button" title="Zoom in" onClick={() => zoomBy(1.25)}>+</button>
        <button type="button" title="Fit to screen (F)" onClick={commands.fit}>Fit</button>
        <button type="button" aria-pressed={pop === 'display'} onClick={() => togglePop('display')}>☀ Display</button>
        <button type="button" title="Keyboard shortcuts" aria-pressed={pop === 'keys'} onClick={() => togglePop('keys')}>⌨</button>
      </div>

      {pop === 'display' && (
        <div className="float pop">
          <label>Brightness <input type="range" min="0.4" max="2" step="0.05" value={display.brightness}
                                   onChange={(e) => setDisplay({ ...display, brightness: Number(e.target.value) })} /></label>
          <label>Contrast <input type="range" min="0.4" max="2" step="0.05" value={display.contrast}
                                 onChange={(e) => setDisplay({ ...display, contrast: Number(e.target.value) })} /></label>
          {[['showAnnotations', 'Show annotations'], ['showNames', 'Show class names (L)'], ['fillBoxes', 'Fill boxes']].map(([k, label]) => (
            <label key={k}>{label}<input type="checkbox" checked={display[k]} onChange={() => setDisplay({ ...display, [k]: !display[k] })} /></label>
          ))}
          <button type="button" onClick={() => setDisplay(DEFAULT_DISPLAY)}>Reset</button>
        </div>
      )}
      {pop === 'keys' && (
        <div className="float pop">
          <table><tbody>{KEYS.map(([k, what]) => <tr key={k}><td><kbd>{k}</kbd></td><td>{what}</td></tr>)}</tbody></table>
        </div>
      )}
    </div>
  );
}
