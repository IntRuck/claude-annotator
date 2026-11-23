/* Shared, domain-agnostic UI used by every feature. */
import { useEffect, useId } from 'react';
import './ui.css';

export function LoadingState({ label = 'Loading…' }) {
  return <div className="ui-loading" role="status">{label}</div>;
}

export function ErrorBanner({ error }) {
  if (!error) return null;
  return <div className="ui-error" role="alert">{error.message || 'Something went wrong.'}</div>;
}

export function EmptyState({ children }) {
  return <div className="ui-empty">{children}</div>;
}

/** Modal dialog. Esc or clicking the backdrop calls onClose. */
export function Modal({ title, onClose, actions, children, wide = false }) {
  const titleId = useId();
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="ui-modal" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={`ui-modal-body${wide ? ' wide' : ''}`} role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="ui-modal-head">
          <h2 id={titleId}>{title}</h2>
          {actions}
          <button type="button" onClick={onClose}>Close</button>
        </div>
        {children}
      </div>
    </div>
  );
}
