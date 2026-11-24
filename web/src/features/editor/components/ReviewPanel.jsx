import { useState } from 'react';
import '../styles/editor.css';

const FLAG_REASONS = ['missing boxes', 'bad / loose boxes', 'wrong class', 'all bad, redo', 'unsure', 'other'];

/** Right panel: Approve (R) and Flag for later (G), with a reason and note, like today. */
export default function ReviewPanel({ image, dirty, onApprove, onFlag }) {
  const approved = image.status === 'reviewed';
  const [note, setNote] = useState(image.flagNote);

  const saveNote = () => {
    if (note !== image.flagNote) onFlag(true, image.flagReason, note);
  };

  return (
    <div className="review">
      <button type="button" className={`approve${approved ? ' done' : ''}`} onClick={onApprove}>
        {approved ? '✓ Approved (R = next)' : '✓ Approve (R)'}
      </button>
      <button type="button" className={`flagbtn${image.flagged ? ' on' : ''}`}
              onClick={() => (image.flagged ? onFlag(false, '', '') : onFlag(true, '', ''))}>
        {image.flagged ? '🚩 Flagged (G to unflag)' : '🚩 Flag for later (G)'}
      </button>
      {image.flagged && (
        <div className="flagmore">
          <select aria-label="Flag reason" value={image.flagReason} onChange={(e) => onFlag(true, e.target.value, note)}>
            <option value="">reason...</option>
            {FLAG_REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <input aria-label="Flag note" placeholder="note (optional)" value={note} onChange={(e) => setNote(e.target.value)}
                 onBlur={saveNote} onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }} />
        </div>
      )}
      <div className="dirty-note">{dirty ? 'Unsaved changes · saves when you move on (or press S)' : ''}</div>
    </div>
  );
}
