import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiFetch } from '@/lib/apiClient';
import { getHealth } from './healthApi';

vi.mock('@/lib/apiClient', () => ({ apiFetch: vi.fn() }));

describe('healthApi', () => {
  beforeEach(() => {
    apiFetch.mockReset().mockResolvedValue({});
  });

  it('asks for the report with the warn-below number', async () => {
    await getHealth(4, 25);
    expect(apiFetch).toHaveBeenCalledWith('/projects/4/health?low=25');
  });

  it('warns below 100 boxes by default', async () => {
    await getHealth(4);
    expect(apiFetch).toHaveBeenCalledWith('/projects/4/health?low=100');
  });
});
