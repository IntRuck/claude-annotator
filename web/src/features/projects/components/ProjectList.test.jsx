import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/apiClient';
import { renderWithProviders } from '@/test/renderWithProviders';
import { createProject, listProjects } from '../api/projectsApi';
import ProjectList from './ProjectList';

vi.mock('../api/projectsApi', () => ({ listProjects: vi.fn(), createProject: vi.fn() }));

describe('ProjectList', () => {
  beforeEach(() => {
    listProjects.mockReset();
    createProject.mockReset();
  });

  it('lists projects as links to their workspace', async () => {
    listProjects.mockResolvedValue([{ id: 2, name: 'Shelf B', createdAt: '2026-11-23T00:00:00Z' }]);
    renderWithProviders(<ProjectList />);
    const link = await screen.findByRole('link', { name: /Shelf B/ });
    expect(link).toHaveAttribute('href', '/projects/2');
  });

  it('shows an empty state when there are no projects', async () => {
    listProjects.mockResolvedValue([]);
    renderWithProviders(<ProjectList />);
    expect(await screen.findByText(/No projects yet/)).toBeInTheDocument();
  });

  it('creates a project and refreshes the list', async () => {
    listProjects.mockResolvedValueOnce([]).mockResolvedValue([{ id: 1, name: 'Shelf', createdAt: '2026-11-23T00:00:00Z' }]);
    createProject.mockResolvedValue({ id: 1, name: 'Shelf' });
    renderWithProviders(<ProjectList />);

    await userEvent.type(await screen.findByLabelText('New project name'), 'Shelf');
    await userEvent.click(screen.getByRole('button', { name: 'Create project' }));

    expect(createProject).toHaveBeenCalledWith('Shelf');
    expect(await screen.findByRole('link', { name: /Shelf/ })).toBeInTheDocument();
    expect(screen.getByLabelText('New project name')).toHaveValue('');
  });

  it('shows the server message when creating fails', async () => {
    listProjects.mockResolvedValue([]);
    createProject.mockRejectedValue(new ApiError({ status: 400, code: 'PROJECT_NAME_REQUIRED', detail: 'Give the project a name.' }));
    renderWithProviders(<ProjectList />);

    await userEvent.type(await screen.findByLabelText('New project name'), ' ');
    await userEvent.click(screen.getByRole('button', { name: 'Create project' }));

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Give the project a name.'));
  });
});
