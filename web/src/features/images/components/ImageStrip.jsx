import { EmptyState } from '@/components/ui';
import { thumbUrl } from '../api/imagesApi';
import { FILTERS } from '../lib/filters';
import { positionOf, stepFrom } from '../lib/navigation';
import '../styles/images.css';

function tooltip(image) {
  const flag = image.flagged
    ? `🚩 ${image.flagReason || 'flagged'}${image.flagNote ? `: ${image.flagNote}` : ''}`
    : '';
  return [image.fileName, image.note || image.status, flag].filter(Boolean).join('\n');
}

/** Right panel: filter, position counter and the thumbnail list. */
export default function ImageStrip({ items, counts, filter, currentId, onSelect, onFilterChange }) {
  const position = positionOf(items, currentId);
  const step = (delta) => {
    const id = stepFrom(items, currentId, delta);
    if (id !== null) onSelect(id);
  };

  return (
    <div className="image-strip">
      <div className="strip-counter">
        <button type="button" aria-label="Previous image" onClick={() => step(-1)}>‹</button>
        <span className="num"><span className="pos">{position ?? (items.length ? '–' : 0)}</span> <span className="tot">/ {items.length}</span></span>
        <button type="button" aria-label="Next image" onClick={() => step(1)}>›</button>
      </div>
      <select aria-label="Filter images" className="strip-filter" value={filter} onChange={(e) => onFilterChange(e.target.value)}>
        {FILTERS.map((f) => (
          <option key={f.value} value={f.value}>{`${f.label} (${counts?.[f.value] ?? 0})`}</option>
        ))}
      </select>
      <div className="strip-thumbs">
        {items.length === 0 && (
          <EmptyState>{counts?.all ? 'No images match this filter.' : 'No images yet. Upload some to start.'}</EmptyState>
        )}
        {items.map((image) => (
          <button key={image.id} type="button" className="thumb" title={tooltip(image)}
                  aria-current={image.id === currentId ? 'true' : undefined} onClick={() => onSelect(image.id)}>
            <img src={thumbUrl(image.id)} loading="lazy" alt="" />
            <span className="badges">
              {image.flagged && <span>🚩</span>}
              {image.boxCount > 0 && <span>{image.boxCount}</span>}
            </span>
            <span className="name"><span className={`dot s-${image.status}`} /><span className="n">{image.fileName}</span></span>
          </button>
        ))}
      </div>
    </div>
  );
}
