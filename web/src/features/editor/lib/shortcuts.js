/*
 * Keyboard shortcuts, same keys as today. Returns a command name, { pickClass: i }, or null.
 * Off while typing in a field (Esc leaves the field) and while a dialog is open.
 */
const FIELDS = new Set(['INPUT', 'SELECT', 'TEXTAREA']);

const PLAIN = {
  Delete: 'delete', Backspace: 'delete', r: 'approve', g: 'flag', d: 'next', ArrowRight: 'next',
  a: 'prev', ArrowLeft: 'prev', b: 'boxTool', v: 'panTool', h: 'solo', f: 'fit', l: 'names', Escape: 'deselect',
};

export function commandFor(event, { dialogOpen = false } = {}) {
  if (FIELDS.has(event.target?.tagName)) return event.key === 'Escape' ? 'blur' : null;
  if (dialogOpen) return null;

  const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
  const mod = event.ctrlKey || event.metaKey;
  if (key === ' ') return 'panHold';
  if (mod && key === 'z' && !event.shiftKey) return 'undo';
  if (mod && (key === 'y' || (key === 'z' && event.shiftKey))) return 'redo';
  if (key === 's') return 'save';
  if (mod) return null;
  if (/^[1-9]$/.test(key)) return { pickClass: Number(key) - 1 };
  return PLAIN[key] ?? null;
}
