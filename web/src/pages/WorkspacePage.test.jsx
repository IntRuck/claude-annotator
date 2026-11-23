import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/renderWithProviders';
import { getProject } from '@/features/projects/api/projectsApi';
import { listClasses } from '@/features/classes/api/classesApi';
import { listImages } from '@/features/images/api/imagesApi';
import WorkspacePage from './WorkspacePage';

vi.mock('@/features/projects/api/projectsApi', () => ({ getProject: vi.fn(), listProjects: vi.fn(), createProject: vi.fn() }));
vi.mock('@/features/classes/api/classesApi', () => ({ listClasses: vi.fn(), addClass: vi.fn(), updateClass: vi.fn() }));
vi.mock('@/features/images/api/imagesApi', () => ({
  listImages: vi.fn(),
  uploadImages: vi.fn(),
  thumbUrl: (id) => `/api/images/${id}/thumb`,
  fileUrl: (id) => `/api/images/${id}/file`,
}));

const image = (id, fileName, status = 'unlabeled') => ({
  id, fileName, status, width: 640, height: 480, boxCount: 0, flagged: false, flagReason: '', flagNote: '', note: '',
});
const COUNTS = { all: 2, unlabeled: 1, auto: 1, edited: 0, reviewed: 0, flagged: 0, error: 0 };

function renderPage() {
  return renderWithProviders(<WorkspacePage />, { route: '/projects/4', path: '/projects/:projectId' });
}

describe('WorkspacePage', () => {
  beforeEach(() => {
    getProject.mockReset().mockResolvedValue({ id: 4, name: 'Shelf B', createdAt: '2026-11-23T00:00:00Z' });
    listClasses.mockReset().mockResolvedValue([{ index: 0, name: 'can', detectorPrompt: '', description: '' }]);
    listImages.mockReset().mockImplementation((_, filter) => Promise.resolve({
      items: filter === 'auto' ? [image(2, 'b.jpg', 'auto')] : [image(1, 'a.jpg'), image(2, 'b.jpg', 'auto')],
      counts: COUNTS,
    }));
  });

  it('loads the project from the URL and shows its name and classes', async () => {
    renderPage();
    expect(await screen.findByRole('heading', { name: 'Shelf B' })).toBeInTheDocument();
    expect(getProject).toHaveBeenCalledWith(4);
    expect(await screen.findByRole('button', { name: /can/ })).toBeInTheDocument();
  });

  it('opens the SKU manager from the top bar', async () => {
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: 'SKUs' }));
    expect(screen.getByRole('dialog', { name: 'SKUs to detect' })).toBeInTheDocument();
  });

  it('opens the import dialog from the top bar', async () => {
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: 'Import dataset' }));
    expect(screen.getByRole('dialog', { name: 'Import a dataset' })).toBeInTheDocument();
  });

  it('opens the SKU manager straight away when the project has no classes yet', async () => {
    listClasses.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByRole('dialog', { name: 'SKUs to detect' })).toBeInTheDocument();
  });

  it('the first-time SKU manager can be closed, like today', async () => {
    listClasses.mockResolvedValue([]);
    renderPage();
    const dialog = await screen.findByRole('dialog', { name: 'SKUs to detect' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog', { name: 'SKUs to detect' })).not.toBeInTheDocument();
  });

  it('the first-time SKU manager does not cover the import dialog', async () => {
    listClasses.mockResolvedValue([]);
    renderPage();
    await screen.findByRole('dialog', { name: 'SKUs to detect' });
    await userEvent.click(screen.getByRole('button', { name: 'Import dataset' }));
    expect(screen.getByRole('dialog', { name: 'Import a dataset' })).toBeInTheDocument();
    expect(screen.queryByRole('dialog', { name: 'SKUs to detect' })).not.toBeInTheDocument();
  });

  it('opens the first image once the list loads and shows it in the middle', async () => {
    renderPage();
    const img = await screen.findByRole('img', { name: 'a.jpg' });
    expect(img).toHaveAttribute('src', '/api/images/1/file');
    expect(screen.getByRole('button', { name: /a\.jpg/ })).toHaveAttribute('aria-current', 'true');
  });

  it('switching to a filter the current image is not in opens the first image of that filter', async () => {
    renderPage();
    await screen.findByRole('img', { name: 'a.jpg' });
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Filter images' }), 'auto');
    expect(listImages).toHaveBeenLastCalledWith(4, 'auto');
    expect(await screen.findByRole('img', { name: 'b.jpg' })).toBeInTheDocument();
  });
});
