import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiFetch } from '@/lib/apiClient';
import {
  createProject, deleteProject, getProject, listProjects, listProjectSummaries, updateProject,
} from './projectsApi';

vi.mock('@/lib/apiClient', () => ({ apiFetch: vi.fn() }));

describe('projectsApi', () => {
  beforeEach(() => {
    apiFetch.mockReset().mockResolvedValue([]);
  });

  it('lists projects', async () => {
    await listProjects();
    expect(apiFetch).toHaveBeenCalledWith('/projects');
  });

  it('lists projects with their numbers for the projects page', async () => {
    await listProjectSummaries();
    expect(apiFetch).toHaveBeenCalledWith('/project-summaries');
  });

  it('gets one project', async () => {
    await getProject(7);
    expect(apiFetch).toHaveBeenCalledWith('/projects/7');
  });

  it('creates a project with POST, with its description', async () => {
    await createProject({ name: 'Shelf', description: 'Store 3' });
    expect(apiFetch).toHaveBeenCalledWith('/projects', { method: 'POST', body: { name: 'Shelf', description: 'Store 3' } });
  });

  it('changes a project with PATCH', async () => {
    await updateProject(7, { name: 'Shelf A', description: '' });
    expect(apiFetch).toHaveBeenCalledWith('/projects/7', { method: 'PATCH', body: { name: 'Shelf A', description: '' } });
  });

  it('deletes a project', async () => {
    await deleteProject(7);
    expect(apiFetch).toHaveBeenCalledWith('/projects/7', { method: 'DELETE' });
  });
});
