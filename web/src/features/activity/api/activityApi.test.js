import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiFetch } from '@/lib/apiClient';
import { listActivity } from './activityApi';

vi.mock('@/lib/apiClient', () => ({ apiFetch: vi.fn() }));

describe('activityApi', () => {
  beforeEach(() => {
    apiFetch.mockReset().mockResolvedValue([]);
  });

  it('reads the latest 100 entries by default', async () => {
    await listActivity(4);
    expect(apiFetch).toHaveBeenCalledWith('/projects/4/activity?limit=100');
  });
});
