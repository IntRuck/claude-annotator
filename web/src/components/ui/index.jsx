/* Shared, domain-agnostic UI used by every feature. */
import { useEffect, useId, useRef, useState } from 'react';
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

/**
 * A button that opens a small list of actions. `label` names the button for screen readers (the visible content is
 * `children`, e.g. "⋯"); `items` are { label, onSelect, danger? } or { separator: true }. Esc, Tab or a click outside
 * closes it; arrow keys move. Keys pressed inside stop here, so page-wide shortcuts (the editor's) don't fire.
 */
export function Menu({ label, items, children, title, align = 'start', className = '' }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const triggerRef = useRef(null);
  const listRef = useRef(null);
  const listId = useId();

  useEffect(() => {
    if (!open) return undefined;
    listRef.current?.querySelector('[role="menuitem"]')?.focus();
    const onPointer = (e) => { if (!rootRef.current?.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onPointer);
    return () => document.removeEventListener('mousedown', onPointer);
  }, [open]);

  const close = (refocus) => {
    setOpen(false);
    if (refocus) triggerRef.current?.focus();
  };

  const onKeyDown = (e) => {
    e.stopPropagation();
    const entries = [...listRef.current.querySelectorAll('[role="menuitem"]')];
    const at = entries.indexOf(document.activeElement);
    const move = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: entries.length - 1 }[e.key];
    if (move !== undefined) {
      e.preventDefault();
      entries[(move + entries.length) % entries.length]?.focus();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      close(true);
    } else if (e.key === 'Tab') {
      close(false);
    }
  };

  const choose = (item) => {
    close(true);
    item.onSelect();
  };

  return (
    <div className={`ui-menu ${className}`.trim()} ref={rootRef}>
      <button type="button" ref={triggerRef} aria-label={label} title={title} aria-haspopup="menu" aria-expanded={open}
              aria-controls={open ? listId : undefined} onClick={() => setOpen((o) => !o)}>
        {children}
      </button>
      {open && (
        <div className={`ui-menu-list ${align}`} role="menu" id={listId} aria-label={label} ref={listRef}
             onKeyDown={onKeyDown}>
          {items.map((item, i) => (item.separator
            ? <hr key={`sep-${i}`} />
            : (
              <button key={item.label} type="button" role="menuitem" tabIndex={-1}
                      className={item.danger ? 'danger' : undefined} onClick={() => choose(item)}>
                {item.label}
              </button>
            )))}
        </div>
      )}
    </div>
  );
}
