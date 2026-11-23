import { EmptyState } from '@/components/ui';
import { classColor } from '../lib/classColor';
import '../styles/classes.css';

/** Class picker in the left panel. Keys 1-9 pick the first nine classes. */
export default function ClassList({ classes, currentIndex, counts = {}, onPick, onOpenSkus }) {
  if (classes.length === 0) {
    return (
      <EmptyState>
        No SKUs yet. <button type="button" onClick={onOpenSkus}>Add SKUs</button>
      </EmptyState>
    );
  }
  return (
    <div className="class-list">
      {classes.map((c) => (
        <button key={c.index} type="button" className="class-row" aria-pressed={c.index === currentIndex}
                title={[`ID ${c.index}`, c.description && `Description: ${c.description}`].filter(Boolean).join('\n')}
                onClick={() => onPick(c.index)}>
          <span className="key">{c.index < 9 ? c.index + 1 : ''}</span>
          <span className="dot" style={{ background: classColor(c.index) }} />
          <span className="nm">{c.name}</span>
          <span className="cnt">{counts[c.index] ?? 0}</span>
        </button>
      ))}
    </div>
  );
}
