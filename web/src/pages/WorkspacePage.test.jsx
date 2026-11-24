import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/apiClient';
import { renderWithProviders } from '@/test/renderWithProviders';
import { FakeEventSource } from '@/test/fakeEventSource';
import { getProject } from '@/features/projects/api/projectsApi';
import { listClasses } from '@/features/classes/api/classesApi';
import { listImages, setFlag } from '@/features/images/api/imagesApi';
import { getBoxes, saveBoxes } from '@/features/editor/api/labelsApi';
import WorkspacePage from './WorkspacePage';

vi.mock('react-konva', () => import('@/test/konvaStub'));
vi.mock('@/features/projects/api/projectsApi', () => ({ getProject: vi.fn(), listProjects: vi.fn(), createProject: vi.fn() }));
vi.mock('@/features/classes/api/classesApi', () => ({ listClasses: vi.fn(), addClass: vi.fn(), updateClass: vi.fn() }));
vi.mock('@/features/images/api/imagesApi', () => ({
  listImages: vi.fn(),
  uploadImages: vi.fn(),
  setFlag: vi.fn(),
  thumbUrl: (id) => `/api/images/${id}/thumb`,
  fileUrl: (id) => `/api/images/${id}/file`,
}));
vi.mock('@/features/editor/api/labelsApi', () => ({ getBoxes: vi.fn(), saveBoxes: vi.fn() }));

const image = (id, fileName, status = 'unlabeled', extra = {}) => ({
  id, projectId: 4, fileName, status, width: 640, height: 480, boxCount: 0, flagged: false, flagReason: '', flagNote: '',
  note: '', updatedAt: `T${id}`, ...extra,
});
const COUNTS = { all: 2, unlabeled: 1, auto: 1, edited: 0, reviewed: 0, flagged: 0, error: 0 };
const BOX = { cls: 0, x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5, source: 'ai', conf: 0.9 };

function renderPage() {
  return renderWithProviders(<WorkspacePage />, { route: '/projects/4', path: '/projects/:projectId' });
}

const stageImage = () => screen.getByTestId('stage-image');

async function waitForImage(id) {
  await waitFor(() => expect(stageImage()).toHaveAttribute('src', `/api/images/${id}/file`));
  await waitFor(() => expect(getBoxes).toHaveBeenLastCalledWith(id));
}

describe('WorkspacePage', () => {
  beforeEach(() => {
    getProject.mockReset().mockResolvedValue({ id: 4, name: 'Shelf B', createdAt: '2026-11-23T00:00:00Z' });
    listClasses.mockReset().mockResolvedValue([{ index: 0, name: 'can', detectorPrompt: '', description: '' },
      { index: 1, name: 'jar', detectorPrompt: '', description: '' }]);
    listImages.mockReset().mockImplementation((_, filter) => Promise.resolve({
      items: filter === 'auto' ? [image(2, 'b.jpg', 'auto')] : [image(1, 'a.jpg'), image(2, 'b.jpg', 'auto')],
      counts: COUNTS,
    }));
    getBoxes.mockReset().mockImplementation((id) => Promise.resolve({ boxes: id === 1 ? [BOX] : [], updatedAt: `T${id}` }));
    saveBoxes.mockReset().mockImplementation((id, body) => Promise.resolve({
      image: image(id, id === 1 ? 'a.jpg' : 'b.jpg', body.status, { updatedAt: `T${id}-saved` }), boxes: body.boxes,
    }));
    setFlag.mockReset().mockResolvedValue(image(1, 'a.jpg', 'unlabeled', { flagged: true }));
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

  it('opens the first image in the editor once the list loads', async () => {
    renderPage();
    await waitForImage(1);
    expect(screen.getByRole('button', { name: /a\.jpg/ })).toHaveAttribute('aria-current', 'true');
  });

  it('switching to a filter the current image is not in opens the first image of that filter', async () => {
    renderPage();
    await waitForImage(1);
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Filter images' }), 'auto');
    await waitForImage(2);
  });

  it('S saves as edited with the version the boxes were loaded at', async () => {
    renderPage();
    await waitForImage(1);
    await userEvent.keyboard('s');
    await waitFor(() => expect(saveBoxes).toHaveBeenCalledWith(1, { boxes: [BOX], status: 'edited', expectedUpdatedAt: 'T1' }));
  });

  it('R approves (saves as reviewed) and opens the next image', async () => {
    renderPage();
    await waitForImage(1);
    await userEvent.keyboard('r');
    await waitFor(() => expect(saveBoxes).toHaveBeenCalledWith(1, expect.objectContaining({ status: 'reviewed' })));
    await waitForImage(2);
  });

  it('D moves to the next image without saving when nothing changed', async () => {
    renderPage();
    await waitForImage(1);
    await userEvent.keyboard('d');
    await waitForImage(2);
    expect(saveBoxes).not.toHaveBeenCalled();
  });

  it('unsaved changes are saved as edited before moving on', async () => {
    renderPage();
    await waitForImage(1);
    await userEvent.keyboard('2'); // pick class "jar": nothing selected yet, so nothing changes
    await userEvent.click(screen.getByRole('tab', { name: /^Boxes/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Delete box' }));
    await userEvent.keyboard('d');
    await waitFor(() => expect(saveBoxes).toHaveBeenCalledWith(1, { boxes: [], status: 'edited', expectedUpdatedAt: 'T1' }));
    await waitForImage(2);
  });

  it('G flags the image for later', async () => {
    renderPage();
    await waitForImage(1);
    await userEvent.keyboard('g');
    await waitFor(() => expect(setFlag).toHaveBeenCalledWith(1, { flagged: true, reason: '', note: '' }));
  });

  it('a newer save by someone else shows a conflict with a Reload button, and keeps you on the image', async () => {
    saveBoxes.mockRejectedValue(new ApiError({ status: 409, code: 'STALE_IMAGE', detail: 'changed since you opened it' }));
    renderPage();
    await waitForImage(1);
    await userEvent.click(screen.getByRole('tab', { name: /^Boxes/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Delete box' }));
    await userEvent.keyboard('d');
    expect(await screen.findByText(/changed since you opened it/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument();
    expect(stageImage()).toHaveAttribute('src', '/api/images/1/file');
  });

  describe('live updates', () => {
    beforeEach(() => {
      FakeEventSource.instances = [];
      vi.stubGlobal('EventSource', FakeEventSource);
    });
    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it('shows when it is connected', async () => {
      renderPage();
      expect(await screen.findByText('Connecting…')).toBeInTheDocument();
      expect(FakeEventSource.latest().url).toBe('/api/projects/4/events');
      act(() => FakeEventSource.latest().open());
      expect(await screen.findByText('Live')).toBeInTheDocument();
    });

    it('an image labelled elsewhere changes in the strip and the counts without a refresh', async () => {
      const { client } = renderPage();
      await waitForImage(1);
      act(() => FakeEventSource.latest().open());
      await waitFor(() => expect(client.isFetching()).toBe(0));

      act(() => FakeEventSource.latest().emit({
        type: 'images', op: 'update', data: image(2, 'b.jpg', 'reviewed', { boxCount: 4, updatedAt: 'T2-ai' }),
      }));

      await waitFor(() => expect(within(screen.getByRole('button', { name: /b\.jpg/ })).getByText('4')).toBeInTheDocument());
      expect(screen.getByRole('option', { name: 'Approved (1)' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Labeled by AI (not checked) (0)' })).toBeInTheDocument();
    });
  });
});
