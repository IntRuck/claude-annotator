/**
 * The only place that reads VITE_* values.
 *
 * Local dev: leave VITE_API_BASE_URL unset; the browser calls /api on the same origin and Vite proxies it
 * to the FastAPI backend (see vite.config.js). The SSE stream uses the same base, so there is no WS URL.
 */
export const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';
