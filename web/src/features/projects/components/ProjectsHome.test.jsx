import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/apiClient';
import { renderWithProviders } from '@/test/renderWithProviders';
import { createProject, deleteProject, listProjectSummaries, updateProject } from '../api/projectsApi';
import ProjectsHome from './ProjectsHome';

vi.mock('../api/projectsApi', () => ({
  listProjects: vi.fn(), listProjectSummaries: vi.fn(), createProject: vi.fn(), updateProject: vi.fn(),
  deleteProject: vi.fn(),
}));

const summary = (id, name, extra = {}) => ({
  id, name, description: '', createdAt: '2026-11-01T00:00:00Z', updatedAt: '2026-11-01T00:00:00Z',
  imageCount: 0, unlabeled: 0, labelled: 0, reviewed: 0, toApprove: 0, flagged: 0, errors: 0, classCount: 0,
  coverImageId: null, lastChangedAt: '2026-11-01T00:00:00Z', ...extra,
});
const SHELF = summary(1, 'Shelf A', {
  description: 'Store 3 shelves', imageCount: 240, unlabeled: 48, labelled: 192, reviewed: 144, toApprove: 48,
  flagged: 2, classCount: 12, coverImageId: 9, lastChangedAt: '2026-11-24T00:00:00Z',
});
const EMPTY = summary(2, 'test');

const card = (name) => screen.getByRole('link', { name }).closest('li');

async function openRowMenu(name, item) {
  await userEvent.click(await screen.findByRole('button', { name: `Actions for ${name}` }));
  await userEvent.click(screen.getByRole('menuitem', { name: item }));
}

describe('ProjectsHome', () => {
  beforeEach(() => {
    listProjectSummaries.mockReset().mockResolvedValue([SHELF, EMPTY]);
    createProject.mockReset();
    updateProject.mockReset();
    deleteProject.mockReset();
  });

  it('shows each project as a card that opens its workspace', async () => {
    renderWithProviders(<ProjectsHome />);
    expect(await screen.findByRole('link', { name: 'Shelf A' })).toHaveAttribute('href', '/projects/1');
    expect(screen.getByRole('link', { name: 'test' })).toHaveAttribute('href', '/projects/2');
  });

  it('a card shows the description, numbers, progress and cover photo', async () => {
    renderWithProviders(<ProjectsHome />);
    await screen.findByRole('link', { name: 'Shelf A' });
    const shelf = within(card('Shelf A'));
    expect(shelf.getByText('Store 3 shelves')).toBeInTheDocument();
    expect(shelf.getByText('240 images')).toBeInTheDocument();
    expect(shelf.getByText('12 SKUs')).toBeInTheDocument();
    expect(shelf.getByText('48 to approve')).toBeInTheDocument();
    expect(shelf.getByText('2 flagged')).toBeInTheDocument();
    expect(shelf.getByText('80% labelled, 60% approved')).toBeInTheDocument();
    expect(card('Shelf A').querySelector('img')).toHaveAttribute('src', '/api/images/9/thumb');
  });

  it('a project without photos says so and hides the zero counts', async () => {
    renderWithProviders(<ProjectsHome />);
    await screen.findByRole('link', { name: 'test' });
    const empty = within(card('test'));
    expect(empty.getByText('No photos yet')).toBeInTheDocument();
    expect(empty.getByText('Upload photos to start')).toBeInTheDocument();
    expect(empty.queryByText(/flagged/)).not.toBeInTheDocument();
    expect(empty.queryByText(/to approve/)).not.toBeInTheDocument();
    expect(card('test').querySelector('img')).toBeNull();
  });

  it('shows an empty state when there are no projects', async () => {
    listProjectSummaries.mockResolvedValue([]);
    renderWithProviders(<ProjectsHome />);
    expect(await screen.findByText(/No projects yet/)).toBeInTheDocument();
  });

  it('search filters by name or description', async () => {
    renderWithProviders(<ProjectsHome />);
    await screen.findByRole('link', { name: 'Shelf A' });
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search projects' }), 'store');
    expect(screen.getByRole('link', { name: 'Shelf A' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'test' })).not.toBeInTheDocument();
  });

  it('says when no project matches the search', async () => {
    renderWithProviders(<ProjectsHome />);
    await screen.findByRole('link', { name: 'Shelf A' });
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search projects' }), 'zzz');
    expect(screen.getByText('No projects match “zzz”.')).toBeInTheDocument();
  });

  it('sorts by name', async () => {
    listProjectSummaries.mockResolvedValue([
      summary(1, 'Zebra', { lastChangedAt: '2026-11-24T00:00:00Z' }), summary(2, 'Apple'),
    ]);
    renderWithProviders(<ProjectsHome />);
    await screen.findByRole('link', { name: 'Zebra' });
    const names = () => screen.getAllByRole('link').map((a) => a.textContent);
    expect(names()).toEqual(['Zebra', 'Apple']);
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Sort projects' }), 'name');
    expect(names()).toEqual(['Apple', 'Zebra']);
  });

  it('creates a project with a description and refreshes the list', async () => {
    createProject.mockResolvedValue(summary(3, 'Fridge'));
    renderWithProviders(<ProjectsHome />);
    await userEvent.click(await screen.findByRole('button', { name: 'New project' }));
    const dialog = screen.getByRole('dialog', { name: 'New project' });
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Fridge');
    await userEvent.type(within(dialog).getByLabelText(/Description/), 'Drinks');
    listProjectSummaries.mockResolvedValue([SHELF, EMPTY, summary(3, 'Fridge')]);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create project' }));

    expect(createProject).toHaveBeenCalledWith({ name: 'Fridge', description: 'Drinks' });
    expect(await screen.findByRole('link', { name: 'Fridge' })).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows the server message in the dialog when creating fails', async () => {
    createProject.mockRejectedValue(
      new ApiError({ status: 400, code: 'PROJECT_NAME_REQUIRED', detail: 'Give the project a name.' }));
    renderWithProviders(<ProjectsHome />);
    await userEvent.click(await screen.findByRole('button', { name: 'New project' }));
    const dialog = screen.getByRole('dialog', { name: 'New project' });
    await userEvent.type(within(dialog).getByLabelText('Name'), ' ');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create project' }));
    await waitFor(() => expect(within(dialog).getByRole('alert')).toHaveTextContent('Give the project a name.'));
  });

  it('edits a project’s name and description from its menu', async () => {
    updateProject.mockResolvedValue({ ...SHELF, name: 'Shelf B' });
    renderWithProviders(<ProjectsHome />);
    await openRowMenu('Shelf A', 'Edit details');
    const dialog = screen.getByRole('dialog', { name: 'Edit project' });
    const name = within(dialog).getByLabelText('Name');
    expect(name).toHaveValue('Shelf A');
    expect(within(dialog).getByLabelText(/Description/)).toHaveValue('Store 3 shelves');
    await userEvent.clear(name);
    await userEvent.type(name, 'Shelf B');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }));

    expect(updateProject).toHaveBeenCalledWith(1, { name: 'Shelf B', description: 'Store 3 shelves' });
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('delete says what goes and needs the project name typed first', async () => {
    deleteProject.mockResolvedValue(null);
    renderWithProviders(<ProjectsHome />);
    await openRowMenu('Shelf A', 'Delete…');
    const dialog = screen.getByRole('dialog', { name: 'Delete Shelf A?' });
    expect(dialog).toHaveTextContent('240 photos');
    expect(dialog).toHaveTextContent('12 SKUs');
    const confirm = within(dialog).getByRole('button', { name: 'Delete project' });
    expect(confirm).toBeDisabled();

    const typed = within(dialog).getByLabelText(/Type the project name/);
    await userEvent.type(typed, 'Shelf');
    expect(confirm).toBeDisabled();
    await userEvent.type(typed, ' A');
    listProjectSummaries.mockResolvedValue([EMPTY]);
    await userEvent.click(confirm);

    expect(deleteProject).toHaveBeenCalledWith(1);
    await waitFor(() => expect(screen.queryByRole('link', { name: 'Shelf A' })).not.toBeInTheDocument());
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('cancelling delete keeps the project', async () => {
    renderWithProviders(<ProjectsHome />);
    await openRowMenu('Shelf A', 'Delete…');
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }));
    expect(deleteProject).not.toHaveBeenCalled();
    expect(screen.getByRole('link', { name: 'Shelf A' })).toBeInTheDocument();
  });
});
