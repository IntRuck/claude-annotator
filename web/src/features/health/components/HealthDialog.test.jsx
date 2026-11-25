import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/apiClient';
import { renderWithProviders } from '@/test/renderWithProviders';
import { getHealth } from '../api/healthApi';
import HealthDialog from './HealthDialog';

vi.mock('../api/healthApi', () => ({ getHealth: vi.fn() }));

const heatmap = Array.from({ length: 20 }, () => Array(20).fill(0));
heatmap[4][4] = 2;
heatmap[14][14] = 1;
const REPORT = {
  summary: {
    images: 4, labeled: 3, boxes: 4, avgBoxesPerImage: 1.3, classes: 2, classesWithData: 2, imbalanceRatio: 3,
    status: { auto: 3, error: 1 },
  },
  classes: [
    { index: 0, name: 'can', boxes: 3, images: 2, avgAreaPct: 2.69, warn: '', imageIds: [1, 3] },
    { index: 1, name: 'bottle', boxes: 1, images: 1, avgAreaPct: 16, warn: 'low (< 100)', imageIds: [1] },
  ],
  sizes: [
    { key: 'tiny', label: 'tiny (<0.1%)', count: 1 }, { key: 'small', label: 'small (0.1-1%)', count: 0 },
    { key: 'medium', label: 'medium (1-10%)', count: 2 }, { key: 'large', label: 'large (>10%)', count: 1 },
  ],
  heatmap,
  issues: [
    { key: 'flagged', label: '🚩 Flagged by you to check later', count: 1, imageIds: [4] },
    { key: 'duplicates', label: 'Possible duplicate boxes (same class, IoU > 0.85)', count: 1, imageIds: [1] },
    { key: 'crowded', label: 'Very crowded (> 100 boxes)', count: 0, imageIds: [] },
  ],
  lowCount: 100,
};

function renderDialog() {
  const handlers = { onClose: vi.fn(), onPickImages: vi.fn() };
  renderWithProviders(<HealthDialog projectId={4} {...handlers} />);
  return handlers;
}

describe('HealthDialog', () => {
  beforeEach(() => {
    getHealth.mockReset().mockResolvedValue(REPORT);
  });

  it('loads the report and shows the summary', async () => {
    renderDialog();
    const dialog = screen.getByRole('dialog', { name: 'Dataset health' });
    expect(await within(dialog).findByText('images (3 labeled)')).toBeInTheDocument();
    expect(getHealth).toHaveBeenCalledWith(4, 100);
    expect(within(dialog).getByText('boxes · 1.3 per image')).toBeInTheDocument();
    expect(within(dialog).getByText('2/2')).toBeInTheDocument();
    expect(within(dialog).getByText('3×')).toBeInTheDocument();
    expect(within(dialog).getByText('Status: auto: 3 · error: 1')).toBeInTheDocument();
  });

  it('lists each class with its boxes, images, size and warning', async () => {
    renderDialog();
    const row = (await screen.findByRole('button', { name: 'bottle' })).closest('tr');
    expect(within(row).getByText('16%')).toBeInTheDocument();
    expect(within(row).getByText('low (< 100)')).toBeInTheDocument();
  });

  it('clicking a class shows its images', async () => {
    const { onPickImages } = renderDialog();
    await userEvent.click(await screen.findByRole('button', { name: 'can' }));
    expect(onPickImages).toHaveBeenCalledWith('Class: can', [1, 3]);
  });

  it('clicking an issue shows its images; an issue with none is not clickable', async () => {
    const { onPickImages } = renderDialog();
    await userEvent.click(await screen.findByRole('button', { name: /Possible duplicate boxes/ }));
    expect(onPickImages).toHaveBeenCalledWith('Possible duplicate boxes (same class, IoU > 0.85)', [1]);
    expect(screen.queryByRole('button', { name: /Very crowded/ })).not.toBeInTheDocument();
    expect(screen.getByText('Very crowded (> 100 boxes)')).toBeInTheDocument();
  });

  it('shows the box sizes with their counts', async () => {
    renderDialog();
    const row = (await screen.findByText('medium (1-10%)')).closest('tr');
    expect(within(row).getByText('2')).toBeInTheDocument();
  });

  it('shows where box centres sit on a 20 by 20 grid', async () => {
    renderDialog();
    const grid = await screen.findByRole('img', { name: 'Where box centres sit' });
    expect(grid.querySelectorAll('.heat-cell')).toHaveLength(400);
    expect(within(grid).getByTitle('2 box centres')).toBeInTheDocument();
  });

  it('reloads the report when the warn-below number changes', async () => {
    renderDialog();
    const input = await screen.findByRole('spinbutton', { name: 'Warn below (boxes)' });
    await userEvent.clear(input);
    await userEvent.type(input, '5');
    await waitFor(() => expect(getHealth).toHaveBeenLastCalledWith(4, 5));
  });

  it('Refresh loads the report again', async () => {
    renderDialog();
    await screen.findByText('images (3 labeled)');
    await userEvent.click(screen.getByRole('button', { name: 'Refresh' }));
    await waitFor(() => expect(getHealth).toHaveBeenCalledTimes(2));
  });

  it('shows the error when the report fails', async () => {
    getHealth.mockReset().mockRejectedValue(new ApiError({ status: 404, code: 'PROJECT_NOT_FOUND', detail: 'Project 4 not found.' }));
    renderDialog();
    expect(await screen.findByRole('alert')).toHaveTextContent('Project 4 not found.');
  });

  it('Close closes it', async () => {
    const { onClose } = renderDialog();
    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalled();
  });
});
