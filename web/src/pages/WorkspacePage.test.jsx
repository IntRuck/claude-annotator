import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/renderWithProviders';
import { getProject } from '@/features/projects/api/projectsApi';
import { listClasses } from '@/features/classes/api/classesApi';
import WorkspacePage from './WorkspacePage';

vi.mock('@/features/projects/api/projectsApi', () => ({ getProject: vi.fn(), listProjects: vi.fn(), createProject: vi.fn() }));
vi.mock('@/features/classes/api/classesApi', () => ({ listClasses: vi.fn(), addClass: vi.fn(), updateClass: vi.fn() }));

describe('WorkspacePage', () => {
  beforeEach(() => {
    getProject.mockReset().mockResolvedValue({ id: 4, name: 'Shelf B', createdAt: '2026-11-23T00:00:00Z' });
    listClasses.mockReset().mockResolvedValue([{ index: 0, name: 'can', detectorPrompt: '', description: '' }]);
  });

  it('loads the project from the URL and shows its name and classes', async () => {
    renderWithProviders(<WorkspacePage />, { route: '/projects/4', path: '/projects/:projectId' });
    expect(await screen.findByRole('heading', { name: 'Shelf B' })).toBeInTheDocument();
    expect(getProject).toHaveBeenCalledWith(4);
    expect(await screen.findByRole('button', { name: /can/ })).toBeInTheDocument();
  });

  it('opens the SKU manager from the top bar', async () => {
    renderWithProviders(<WorkspacePage />, { route: '/projects/4', path: '/projects/:projectId' });
    await userEvent.click(await screen.findByRole('button', { name: 'SKUs' }));
    expect(screen.getByRole('dialog', { name: 'SKUs to detect' })).toBeInTheDocument();
  });

  it('opens the SKU manager straight away when the project has no classes yet', async () => {
    listClasses.mockResolvedValue([]);
    renderWithProviders(<WorkspacePage />, { route: '/projects/4', path: '/projects/:projectId' });
    expect(await screen.findByRole('dialog', { name: 'SKUs to detect' })).toBeInTheDocument();
  });
});
