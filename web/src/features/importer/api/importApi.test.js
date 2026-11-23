import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiFetch } from '@/lib/apiClient';
import { importDataset } from './importApi';

vi.mock('@/lib/apiClient', () => ({ apiFetch: vi.fn() }));

function fileAt(path) {
  const file = new File(['x'], path.split('/').pop());
  Object.defineProperty(file, 'webkitRelativePath', { value: path });
  return file;
}

describe('importDataset', () => {
  beforeEach(() => {
    apiFetch.mockReset().mockResolvedValue({});
  });

  it('sends every file with its folder path so the server can match labels to images', async () => {
    await importDataset(4, [fileAt('shelf/images/a.jpg'), fileAt('shelf/labels/a.txt'), new File(['y'], 'classes.txt')]);

    const [path, options] = apiFetch.mock.calls[0];
    expect(path).toBe('/projects/4/import');
    expect(options.method).toBe('POST');
    expect(options.body.getAll('files').map((f) => f.name)).toEqual(['shelf/images/a.jpg', 'shelf/labels/a.txt', 'classes.txt']);
  });
});
