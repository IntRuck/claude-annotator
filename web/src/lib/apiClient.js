import { API_BASE } from '@/config/env';

/** Error thrown for any non-2xx response. Carries the backend's problem+json fields. */
export class ApiError extends Error {
  constructor({ status, code, detail, traceId, errors }) {
    super(detail || `Request failed (${status})`);
    this.name = 'ApiError';
    this.status = status;
    this.code = code || 'HTTP_ERROR';
    this.traceId = traceId;
    this.errors = errors || [];
  }
}

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && Object.getPrototypeOf(value) === Object.prototype;
}

async function readProblem(response) {
  const type = response.headers.get('Content-Type') || '';
  if (type.includes('json')) {
    try {
      return await response.json();
    } catch {
      return {};
    }
  }
  return {};
}

/**
 * Calls the backend API. `path` is relative to API_BASE (e.g. '/projects').
 * A plain-object `body` is sent as JSON; FormData is sent as-is (multipart upload).
 * Resolves to the parsed JSON (null for 204); rejects with ApiError.
 */
export async function apiFetch(path, { body, headers, ...options } = {}) {
  const requestHeaders = new Headers(headers);
  let requestBody = body;
  if (isPlainObject(body) || Array.isArray(body)) {
    requestBody = JSON.stringify(body);
    requestHeaders.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers: requestHeaders, body: requestBody });

  if (!response.ok) {
    const problem = await readProblem(response);
    throw new ApiError({ ...problem, status: response.status });
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}
