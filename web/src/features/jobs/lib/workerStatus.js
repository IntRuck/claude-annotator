/** The worker beats every 15 s; three missed beats means it's gone (same rule as the API). */
export const OFFLINE_AFTER_MS = 45000;

/** true / false, or null while the status hasn't loaded. Uses the last heartbeat, so a worker that stops is
 * noticed by the page's own clock, without asking the server. */
export function isWorkerOnline(status, now) {
  if (!status) return null;
  if (!status.lastSeenAt) return false;
  return now - Date.parse(status.lastSeenAt) <= OFFLINE_AFTER_MS;
}
