/** One line for the engine bar: what the AI is doing now. */
export function statusText(summary) {
  const running = summary?.running?.[0];
  const queued = summary?.queued ?? 0;
  if (running) return `Labeling ${running.fileName}…${queued ? ` · ${queued} waiting` : ''}`;
  return queued ? `${queued} waiting` : 'idle';
}

/** What to tell the user when a run button found nothing to do (empty when it queued something). */
export function noticeFor({ matched, queued }) {
  if (matched === 0) return 'Nothing to label';
  if (queued === 0) return 'Already queued';
  return '';
}
