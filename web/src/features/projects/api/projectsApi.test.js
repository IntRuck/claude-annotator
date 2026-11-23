import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiFetch } from '@/lib/apiClient';
import { createProject, getProject, listProjects } from './projectsApi';

vi.mock('@/lib/apiClient', () => ({ apiFetch: vi.fn() }));

describe('projectsApi', () => {
  beforeEach(() => {
    apiFetch.mockReset().mockResolvedValue([]);
  });

  it('lists projects', async () => {
    await listProjects();
    expect(apiFetch).toHaveBeenCalledWith('/projects');
  });

  it('gets one project', async () => {
    await getProject(7);
    expect(apiFetch).toHaveBeenCalledWith('/projects/7');
  });

  it('creates a project with POST', async () => {
    await createProject('Shelf');
    expect(apiFetch).toHaveBeenCalledWith('/projects', { method: 'POST', body: { name: 'Shelf' } });
  });
});
