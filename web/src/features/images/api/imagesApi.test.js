import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiFetch } from '@/lib/apiClient';
import { fileUrl, listImages, thumbUrl, uploadImages } from './imagesApi';

vi.mock('@/lib/apiClient', () => ({ apiFetch: vi.fn() }));

describe('imagesApi', () => {
  beforeEach(() => {
    apiFetch.mockReset().mockResolvedValue({});
  });

  it('lists a project\'s images for one filter', async () => {
    await listImages(3, 'flagged');
    expect(apiFetch).toHaveBeenCalledWith('/projects/3/images?filter=flagged');
  });

  it('uploads files as multipart form data under "files"', async () => {
    const a = new File(['a'], 'a.jpg', { type: 'image/jpeg' });
    const b = new File(['b'], 'b.png', { type: 'image/png' });

    await uploadImages(3, [a, b]);

    const [path, options] = apiFetch.mock.calls[0];
    expect(path).toBe('/projects/3/images');
    expect(options.method).toBe('POST');
    expect(options.body).toBeInstanceOf(FormData);
    expect(options.body.getAll('files').map((f) => f.name)).toEqual(['a.jpg', 'b.png']);
  });

  it('builds the thumbnail and full-size image links (the API redirects to Storage)', () => {
    expect(thumbUrl(7)).toBe('/api/images/7/thumb');
    expect(fileUrl(7)).toBe('/api/images/7/file');
  });
});
