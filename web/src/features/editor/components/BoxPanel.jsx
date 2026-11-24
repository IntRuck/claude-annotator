import { EmptyState } from '@/components/ui';
import { classColor } from '@/features/classes';
import '../styles/editor.css';

/** The Boxes tab: every box on this image with its class, show/hide and delete. */
export default function BoxPanel({ boxes, classes, selected, hidden, onSelect, onChangeClass, onDelete, onToggleHidden }) {
  if (boxes.length === 0) {
    return <EmptyState>No boxes. Drag on the image to draw one, or ask the AI to find objects.</EmptyState>;
  }
  const known = new Set(classes.map((c) => c.index));
  return (
    <ul className="box-list">
      {boxes.map((b, i) => (
        // Boxes have no id until saved; their position is their identity while editing.
        <li key={i} className={i === selected ? 'selected' : ''} onMouseEnter={() => onSelect(i)}>
          <span className="dot" style={{ background: classColor(b.cls) }} />
          <select aria-label={`Class of box ${i + 1}`} value={String(b.cls)} onChange={(e) => onChangeClass(i, Number(e.target.value))}>
            {classes.map((c) => <option key={c.index} value={String(c.index)}>{c.name}</option>)}
            {!known.has(b.cls) && <option value={String(b.cls)}>{`ID ${b.cls} (unknown)`}</option>}
          </select>
          <button type="button" className="ghost" aria-label={hidden.has(i) ? 'Show box' : 'Hide box'} onClick={() => onToggleHidden(i)}>
            {hidden.has(i) ? '◌' : '👁'}
          </button>
          <button type="button" className="ghost" aria-label="Delete box" onClick={() => onDelete(i)}>✕</button>
        </li>
      ))}
    </ul>
  );
}
