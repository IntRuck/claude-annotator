import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiFetch } from '@/lib/apiClient';
import { addClass, listClasses, updateClass } from './classesApi';

vi.mock('@/lib/apiClient', () => ({ apiFetch: vi.fn() }));

describe('classesApi', () => {
  beforeEach(() => {
    apiFetch.mockReset().mockResolvedValue({});
  });

  it('lists the classes of a project', async () => {
    await listClasses(3);
    expect(apiFetch).toHaveBeenCalledWith('/projects/3/classes');
  });

  it('adds a class with POST', async () => {
    await addClass(3, { name: 'can', detectorPrompt: 'metal can', description: '' });
    expect(apiFetch).toHaveBeenCalledWith('/projects/3/classes', {
      method: 'POST',
      body: { name: 'can', detectorPrompt: 'metal can', description: '' },
    });
  });

  it('updates only the fields given with PATCH', async () => {
    await updateClass(3, 0, { description: 'Silver' });
    expect(apiFetch).toHaveBeenCalledWith('/projects/3/classes/0', { method: 'PATCH', body: { description: 'Silver' } });
  });
});
