import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiFetch } from '@/lib/apiClient';

function jsonResponse(status, body, contentType = 'application/json') {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': contentType } });
}

describe('apiFetch', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('calls the API base path and returns the parsed JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { status: 'ok' }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiFetch('/health')).resolves.toEqual({ status: 'ok' });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/health');
  });

  it('sends a plain object body as JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, { id: 1 }));
    vi.stubGlobal('fetch', fetchMock);

    await apiFetch('/projects', { method: 'POST', body: { name: 'Shelf' } });

    const [, options] = fetchMock.mock.calls[0];
    expect(options.method).toBe('POST');
    expect(options.body).toBe('{"name":"Shelf"}');
    expect(new Headers(options.headers).get('Content-Type')).toBe('application/json');
  });

  it('sends FormData as-is so the browser sets the multipart boundary', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, {}));
    vi.stubGlobal('fetch', fetchMock);
    const form = new FormData();
    form.append('files', new Blob(['x']), 'a.jpg');

    await apiFetch('/projects/1/images', { method: 'POST', body: form });

    const [, options] = fetchMock.mock.calls[0];
    expect(options.body).toBe(form);
    expect(new Headers(options.headers).has('Content-Type')).toBe(false);
  });

  it('returns null for 204 No Content', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    await expect(apiFetch('/projects/1/jobs/stop', { method: 'POST' })).resolves.toBeNull();
  });

  it('throws ApiError with the problem+json code, detail and traceId', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(
      409,
      { status: 409, code: 'STALE_IMAGE', detail: 'Someone else saved this image.', traceId: 'abc' },
      'application/problem+json',
    )));

    const error = await apiFetch('/images/1/boxes', { method: 'PUT', body: {} }).catch((e) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(409);
    expect(error.code).toBe('STALE_IMAGE');
    expect(error.message).toBe('Someone else saved this image.');
    expect(error.traceId).toBe('abc');
  });

  it('keeps field errors from a validation problem', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(
      400,
      { status: 400, code: 'VALIDATION_FAILED', detail: 'The request is not valid.', errors: [{ field: 'name', message: 'Field required' }] },
      'application/problem+json',
    )));

    const error = await apiFetch('/projects', { method: 'POST', body: {} }).catch((e) => e);

    expect(error.errors).toEqual([{ field: 'name', message: 'Field required' }]);
  });

  it('throws ApiError HTTP_ERROR when the error body is not problem+json', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Bad Gateway', { status: 502 })));

    const error = await apiFetch('/health').catch((e) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(502);
    expect(error.code).toBe('HTTP_ERROR');
  });
});
