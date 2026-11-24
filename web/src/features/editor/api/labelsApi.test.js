import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiFetch } from '@/lib/apiClient';
import { getBoxes, saveBoxes } from './labelsApi';

vi.mock('@/lib/apiClient', () => ({ apiFetch: vi.fn() }));

describe('labelsApi', () => {
  beforeEach(() => {
    apiFetch.mockReset().mockResolvedValue({});
  });

  it('loads an image\'s boxes', async () => {
    await getBoxes(5);
    expect(apiFetch).toHaveBeenCalledWith('/images/5/boxes');
  });

  it('saves the whole box set with the status and the version it was loaded at', async () => {
    const boxes = [{ cls: 0, x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5, source: 'human' }];
    await saveBoxes(5, { boxes, status: 'reviewed', expectedUpdatedAt: 'T1' });
    expect(apiFetch).toHaveBeenCalledWith('/images/5/boxes', {
      method: 'PUT', body: { boxes, status: 'reviewed', expectedUpdatedAt: 'T1' },
    });
  });
});
