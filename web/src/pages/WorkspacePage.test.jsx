import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/apiClient';
import { renderWithProviders } from '@/test/renderWithProviders';
import { FakeEventSource } from '@/test/fakeEventSource';
import { getProject, listProjects, updateProject } from '@/features/projects/api/projectsApi';
import { listClasses } from '@/features/classes/api/classesApi';
import { listImages, setFlag } from '@/features/images/api/imagesApi';
import { getBoxes, saveBoxes } from '@/features/editor/api/labelsApi';
import { getEngineStatus, getJobSummary, queueJobs, resumeWorker } from '@/features/jobs/api/jobsApi';
import { listActivity } from '@/features/activity/api/activityApi';
import { getHealth } from '@/features/health/api/healthApi';
import { getExportSummary } from '@/features/export/api/exportApi';
import WorkspacePage from './WorkspacePage';

vi.mock('react-konva', () => import('@/test/konvaStub'));
vi.mock('@/features/projects/api/projectsApi', () => ({
  getProject: vi.fn(), listProjects: vi.fn(), listProjectSummaries: vi.fn(), createProject: vi.fn(), updateProject: vi.fn(),
  deleteProject: vi.fn(),
}));
vi.mock('@/features/classes/api/classesApi', () => ({ listClasses: vi.fn(), addClass: vi.fn(), updateClass: vi.fn() }));
vi.mock('@/features/images/api/imagesApi', () => ({
  listImages: vi.fn(),
  uploadImages: vi.fn(),
  setFlag: vi.fn(),
  thumbUrl: (id) => `/api/images/${id}/thumb`,
  fileUrl: (id) => `/api/images/${id}/file`,
}));
vi.mock('@/features/editor/api/labelsApi', () => ({ getBoxes: vi.fn(), saveBoxes: vi.fn() }));
vi.mock('@/features/jobs/api/jobsApi', () => ({
  getJobSummary: vi.fn(), queueJobs: vi.fn(), stopJobs: vi.fn(), getEngineStatus: vi.fn(), resumeWorker: vi.fn(),
}));
vi.mock('@/features/activity/api/activityApi', () => ({ listActivity: vi.fn() }));
vi.mock('@/features/health/api/healthApi', () => ({ getHealth: vi.fn() }));
vi.mock('@/features/export/api/exportApi', async (importOriginal) => ({ ...(await importOriginal()), getExportSummary: vi.fn() }));

const image = (id, fileName, status = 'unlabeled', extra = {}) => ({
  id, projectId: 4, fileName, status, width: 640, height: 480, boxCount: 0, flagged: false, flagReason: '', flagNote: '',
  note: '', updatedAt: `T${id}`, ...extra,
});
const COUNTS = { all: 2, unlabeled: 1, auto: 1, edited: 0, reviewed: 0, flagged: 0, error: 0 };
const BOX = { cls: 0, x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5, source: 'ai', conf: 0.9 };
const TINY = 'Tiny boxes (< 0.5% width or height)';
const HEALTH = {
  summary: { images: 2, labeled: 1, boxes: 1, avgBoxesPerImage: 1, classes: 2, classesWithData: 1, imbalanceRatio: 1,
             status: { unlabeled: 1, auto: 1 } },
  classes: [{ index: 0, name: 'can', boxes: 1, images: 1, avgAreaPct: 16, warn: 'low (< 100)', imageIds: [2] },
            { index: 1, name: 'jar', boxes: 0, images: 0, avgAreaPct: 0, warn: 'no boxes', imageIds: [] }],
  sizes: [], heatmap: [[0]], lowCount: 100,
  issues: [{ key: 'tiny', label: TINY, count: 1, imageIds: [2] }],
};

function renderPage() {
  return renderWithProviders(<WorkspacePage />, {
    route: '/projects/4', path: '/projects/:projectId', routes: { '/': <p>Projects page</p> },
  });
}

/** Import dataset, SKUs and Edit project details sit in the top bar's ⋯ menu. */
async function openTool(name) {
  await userEvent.click(await screen.findByRole('button', { name: 'More' }));
  await userEvent.click(screen.getByRole('menuitem', { name }));
}

const PROJECTS = { 4: { id: 4, name: 'Shelf B', description: 'Store 3', createdAt: '2026-11-23T00:00:00Z' },
                   5: { id: 5, name: 'Fridge', description: '', createdAt: '2026-11-24T00:00:00Z' } };

const stageImage = () => screen.getByTestId('stage-image');

async function waitForImage(id) {
  await waitFor(() => expect(stageImage()).toHaveAttribute('src', `/api/images/${id}/file`));
  await waitFor(() => expect(getBoxes).toHaveBeenLastCalledWith(id));
}

describe('WorkspacePage', () => {
  beforeEach(() => {
    getProject.mockReset().mockImplementation((id) => Promise.resolve(PROJECTS[id]));
    listProjects.mockReset().mockResolvedValue(Object.values(PROJECTS));
    updateProject.mockReset();
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
    getJobSummary.mockReset().mockResolvedValue({ queued: 0, running: [] });
    queueJobs.mockReset().mockResolvedValue({ matched: 1, queued: 1, alreadyQueued: 0 });
    listActivity.mockReset().mockResolvedValue([]);
    getEngineStatus.mockReset().mockResolvedValue({ workerOnline: true, lastSeenAt: new Date().toISOString(), engines: {}, paused: [] });
    resumeWorker.mockReset().mockResolvedValue({ resumed: ['gemini'] });
    getHealth.mockReset().mockResolvedValue(HEALTH);
    getExportSummary.mockReset().mockResolvedValue({ images: 1, boxes: 1, train: 1, val: 0 });
    localStorage.clear();
  });

  it('loads the project from the URL and shows its name and classes', async () => {
    renderPage();
    expect(await screen.findByRole('heading', { name: 'Shelf B' })).toBeInTheDocument();
    expect(getProject).toHaveBeenCalledWith(4);
    expect(await screen.findByRole('button', { name: /can/ })).toBeInTheDocument();
  });

  it('opens the SKU manager from the top bar', async () => {
    renderPage();
    await openTool('SKUs');
    expect(screen.getByRole('dialog', { name: 'SKUs to detect' })).toBeInTheDocument();
  });

  it('opens the import dialog from the top bar', async () => {
    renderPage();
    await openTool('Import dataset');
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
    await openTool('Import dataset');
    expect(screen.getByRole('dialog', { name: 'Import a dataset' })).toBeInTheDocument();
    expect(screen.queryByRole('dialog', { name: 'SKUs to detect' })).not.toBeInTheDocument();
  });

  it('opens the SKU manager from under the class list', async () => {
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: 'Edit SKUs' }));
    expect(screen.getByRole('dialog', { name: 'SKUs to detect' })).toBeInTheDocument();
  });

  describe('getting around', () => {
    it('← Projects goes back to the projects page', async () => {
      renderPage();
      await userEvent.click(await screen.findByRole('button', { name: '← Projects' }));
      expect(await screen.findByText('Projects page')).toBeInTheDocument();
    });

    it('← Projects saves unsaved edits first', async () => {
      renderPage();
      await waitForImage(1);
      await userEvent.click(screen.getByRole('tab', { name: /^Boxes/ }));
      await userEvent.click(screen.getByRole('button', { name: 'Delete box' }));
      await userEvent.click(screen.getByRole('button', { name: '← Projects' }));
      await waitFor(() => expect(saveBoxes).toHaveBeenCalledWith(1, { boxes: [], status: 'edited', expectedUpdatedAt: 'T1' }));
      expect(await screen.findByText('Projects page')).toBeInTheDocument();
    });

    it('the project name opens the other projects, and switching starts the new one fresh', async () => {
      renderPage();
      await waitForImage(1);
      await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Filter images' }), 'auto');
      await waitForImage(2);

      await userEvent.click(screen.getByRole('button', { name: 'Shelf B' }));
      expect(screen.queryByRole('menuitem', { name: 'Shelf B' })).not.toBeInTheDocument();
      await userEvent.click(screen.getByRole('menuitem', { name: 'Fridge' }));

      expect(await screen.findByRole('heading', { name: 'Fridge' })).toBeInTheDocument();
      expect(getProject).toHaveBeenCalledWith(5);
      await waitFor(() => expect(screen.getByRole('combobox', { name: 'Filter images' })).toHaveValue('all'));
    });

    it('hovering the project name shows the full name (long names are cut) and its description', async () => {
      renderPage();
      expect(await screen.findByRole('button', { name: 'Shelf B' })).toHaveAttribute('title', 'Shelf B\nStore 3');
    });

    it('a project without a description shows just its name on hover', async () => {
      getProject.mockResolvedValue(PROJECTS[5]);
      renderPage();
      expect(await screen.findByRole('button', { name: 'Fridge' })).toHaveAttribute('title', 'Fridge');
    });

    it('the project name menu also leads to all projects', async () => {
      renderPage();
      await userEvent.click(await screen.findByRole('button', { name: 'Shelf B' }));
      await userEvent.click(screen.getByRole('menuitem', { name: 'All projects' }));
      expect(await screen.findByText('Projects page')).toBeInTheDocument();
    });

    it('edits the project details from the ⋯ menu', async () => {
      updateProject.mockResolvedValue({ ...PROJECTS[4], name: 'Shelf C' });
      renderPage();
      await screen.findByRole('heading', { name: 'Shelf B' });
      await openTool('Edit project details');
      const form = screen.getByRole('dialog', { name: 'Edit project' });
      expect(within(form).getByLabelText(/Description/)).toHaveValue('Store 3');
      await userEvent.clear(within(form).getByLabelText('Name'));
      await userEvent.type(within(form).getByLabelText('Name'), 'Shelf C');
      await userEvent.click(within(form).getByRole('button', { name: 'Save changes' }));
      expect(updateProject).toHaveBeenCalledWith(4, { name: 'Shelf C', description: 'Store 3' });
      expect(await screen.findByRole('heading', { name: 'Shelf C' })).toBeInTheDocument();
    });

    it('a project deleted elsewhere says so, with a way back', async () => {
      getProject.mockRejectedValue(new ApiError({ status: 404, code: 'PROJECT_NOT_FOUND', detail: 'Project 4 is gone.' }));
      renderPage();
      expect(await screen.findByText('This project no longer exists.')).toBeInTheDocument();
      await userEvent.click(screen.getByRole('link', { name: 'Back to projects' }));
      expect(await screen.findByText('Projects page')).toBeInTheDocument();
    });
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

    it('says Connecting…, Live and Offline in words', async () => {
      renderPage();
      expect(await screen.findByRole('status', { name: 'Connecting…' })).toHaveTextContent('Connecting…');
      expect(FakeEventSource.latest().url).toBe('/api/projects/4/events');
      act(() => FakeEventSource.latest().open());
      expect(await screen.findByRole('status', { name: 'Live' })).toHaveTextContent('Live');
      act(() => FakeEventSource.latest().fail());
      expect(await screen.findByRole('status', { name: 'Offline' })).toHaveTextContent('Offline');
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

  describe('AI', () => {
    const GEMINI = { engine: 'gemini', options: { model: 'gemini-3.5-flash-lite', extra: '' } };

    it('Label all unlabeled queues the unlabeled images with the chosen engine', async () => {
      renderPage();
      await waitForImage(1);
      await userEvent.click(screen.getByRole('button', { name: 'Label all unlabeled' }));
      await waitFor(() => expect(queueJobs).toHaveBeenCalledWith(4, { target: 'unlabeled', ...GEMINI }));
    });

    it('Find objects with AI saves unsaved edits first, then queues this image', async () => {
      renderPage();
      await waitForImage(1);
      await userEvent.click(screen.getByRole('tab', { name: /^Boxes/ }));
      await userEvent.click(screen.getByRole('button', { name: 'Delete box' }));

      await userEvent.click(screen.getByRole('button', { name: /Find objects with AI/ }));

      await waitFor(() => expect(queueJobs).toHaveBeenCalledWith(4, { target: 'image', imageId: 1, ...GEMINI }));
      expect(saveBoxes).toHaveBeenCalledWith(1, { boxes: [], status: 'edited', expectedUpdatedAt: 'T1' });
      expect(saveBoxes.mock.invocationCallOrder[0]).toBeLessThan(queueJobs.mock.invocationCallOrder[0]);
    });

    it('Refine all queues the AI-labelled images for review', async () => {
      renderPage();
      await waitForImage(1);
      await userEvent.click(screen.getByRole('button', { name: 'Refine all' }));
      await waitFor(() => expect(queueJobs).toHaveBeenCalledWith(4, { kind: 'refine', target: 'auto', ...GEMINI }));
    });

    it('Refine boxes with AI queues this image for review', async () => {
      renderPage();
      await waitForImage(1);
      await userEvent.click(screen.getByRole('button', { name: /Refine boxes with AI/ }));
      await waitFor(() => expect(queueJobs).toHaveBeenCalledWith(4, { kind: 'refine', target: 'image', imageId: 1, ...GEMINI }));
    });

    it('a detector is sent its model and confidence, and can not refine', async () => {
      renderPage();
      await waitForImage(1);
      await userEvent.selectOptions(screen.getByRole('combobox', { name: 'AI engine' }), 'yolo_world');

      await userEvent.click(screen.getByRole('button', { name: 'Label all unlabeled' }));

      await waitFor(() => expect(queueJobs).toHaveBeenCalledWith(4, {
        target: 'unlabeled', engine: 'yolo_world', options: { model: 'yolov8s-worldv2.pt', threshold: 0.25 } }));
      expect(screen.getByRole('button', { name: /Refine boxes with AI/ })).toBeDisabled();
    });

    it('without classes the SKU manager opens instead, like today', async () => {
      listClasses.mockResolvedValue([]);
      renderPage();
      const intro = await screen.findByRole('dialog');
      await userEvent.click(within(intro).getByRole('button', { name: 'Close' }));
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());

      await userEvent.click(screen.getByRole('button', { name: 'Label all unlabeled' }));

      expect(await screen.findByRole('dialog')).toBeInTheDocument();
      expect(queueJobs).not.toHaveBeenCalled();
    });

    it('says when there was nothing to label', async () => {
      queueJobs.mockResolvedValue({ matched: 0, queued: 0, alreadyQueued: 0 });
      renderPage();
      await waitForImage(1);
      await userEvent.click(screen.getByRole('button', { name: 'Label all unlabeled' }));
      expect(await screen.findByText('Nothing to label')).toBeInTheDocument();
    });

    describe('live', () => {
      beforeEach(() => {
        FakeEventSource.instances = [];
        vi.stubGlobal('EventSource', FakeEventSource);
      });
      afterEach(() => {
        vi.unstubAllGlobals();
      });

      async function openLive() {
        const page = renderPage();
        await waitForImage(1);
        act(() => FakeEventSource.latest().open());
        await waitFor(() => expect(page.client.isFetching()).toBe(0));
        return page;
      }

      it('shows what the AI is working on', async () => {
        await openLive();
        act(() => FakeEventSource.latest().emit({
          type: 'jobs', op: 'summary',
          data: { queued: 3, running: [{ id: 9, imageId: 2, fileName: 'b.jpg', engine: 'gemini', kind: 'annotate' }] },
        }));
        expect(await screen.findByText('Labeling b.jpg… · 3 waiting')).toBeInTheDocument();
      });

      it('an engine paused at its usage limit shows a banner, and Resume carries on', async () => {
        await openLive();
        act(() => FakeEventSource.latest().emit({
          type: 'worker', op: 'status',
          data: { workerOnline: true, lastSeenAt: new Date().toISOString(), engines: {},
                  paused: [{ engine: 'gemini', label: 'Gemini', reason: 'Gemini daily free quota used up', pausedAt: 'T' }] },
        }));

        expect(await screen.findByText(/Gemini paused: Gemini daily free quota used up/)).toBeInTheDocument();
        await userEvent.click(screen.getByRole('button', { name: 'Resume' }));
        await waitFor(() => expect(resumeWorker).toHaveBeenCalled());
      });

      it('new activity appears in the log', async () => {
        await openLive();
        act(() => FakeEventSource.latest().emit({
          type: 'activity', op: 'insert',
          data: { id: 5, level: 'info', message: 'b.jpg: 2 box(es) in 1.2s (via gemini)', jobId: 9, imageId: 2,
                  createdAt: '2026-11-24T08:00:00Z' },
        }));
        expect(await screen.findByText('b.jpg: 2 box(es) in 1.2s (via gemini)')).toBeInTheDocument();
      });
    });
  });

  describe('health check', () => {
    it('opens the report from the top bar', async () => {
      renderPage();
      await userEvent.click(await screen.findByRole('button', { name: 'Health check' }));
      const dialog = screen.getByRole('dialog', { name: 'Dataset health' });
      expect(await within(dialog).findByText('images (1 labeled)')).toBeInTheDocument();
      expect(getHealth).toHaveBeenCalledWith(4, 100);
    });

    it('clicking an issue shows just its images as a filter and opens the first', async () => {
      renderPage();
      await waitForImage(1);
      await userEvent.click(screen.getByRole('button', { name: 'Health check' }));
      await userEvent.click(await screen.findByRole('button', { name: TINY }));
      expect(screen.queryByRole('dialog', { name: 'Dataset health' })).not.toBeInTheDocument();
      const select = screen.getByRole('combobox', { name: 'Filter images' });
      expect(select).toHaveValue('custom');
      expect(within(select).getByRole('option', { name: `${TINY} (1)` })).toBeInTheDocument();
      await waitForImage(2);
      expect(screen.queryByRole('button', { name: /a\.jpg/ })).not.toBeInTheDocument();
    });

    it('clicking a class shows the images that have it', async () => {
      renderPage();
      await waitForImage(1);
      await userEvent.click(screen.getByRole('button', { name: 'Health check' }));
      const dialog = screen.getByRole('dialog', { name: 'Dataset health' });
      await userEvent.click(await within(dialog).findByRole('button', { name: 'can' }));
      expect(within(screen.getByRole('combobox', { name: 'Filter images' })).getByRole('option', { name: 'Class: can (1)' }))
        .toBeInTheDocument();
      await waitForImage(2);
    });

    it('saves unsaved edits before opening it', async () => {
      renderPage();
      await waitForImage(1);
      await userEvent.click(screen.getByRole('tab', { name: /^Boxes/ }));
      await userEvent.click(screen.getByRole('button', { name: 'Delete box' }));
      await userEvent.click(screen.getByRole('button', { name: 'Health check' }));
      await waitFor(() => expect(saveBoxes).toHaveBeenCalledWith(1, { boxes: [], status: 'edited', expectedUpdatedAt: 'T1' }));
      expect(await screen.findByRole('dialog', { name: 'Dataset health' })).toBeInTheDocument();
    });
  });

  describe('export', () => {
    it('opens the export dialog from the top bar, with download links for this project', async () => {
      renderPage();
      await userEvent.click(await screen.findByRole('button', { name: 'Export' }));
      expect(screen.getByRole('dialog', { name: 'Export labels' })).toBeInTheDocument();
      expect(await screen.findByRole('link', { name: 'Download YOLO zip' }))
        .toHaveAttribute('href', '/api/projects/4/exports/yolo?onlyReviewed=false&skipFlagged=true');
    });

    it('saves unsaved edits before exporting, so the download has them', async () => {
      renderPage();
      await waitForImage(1);
      await userEvent.click(screen.getByRole('tab', { name: /^Boxes/ }));
      await userEvent.click(screen.getByRole('button', { name: 'Delete box' }));
      await userEvent.click(screen.getByRole('button', { name: 'Export' }));
      await waitFor(() => expect(saveBoxes).toHaveBeenCalledWith(1, { boxes: [], status: 'edited', expectedUpdatedAt: 'T1' }));
      expect(await screen.findByRole('dialog', { name: 'Export labels' })).toBeInTheDocument();
    });
  });
});
