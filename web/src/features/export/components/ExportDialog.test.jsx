import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/apiClient';
import { renderWithProviders } from '@/test/renderWithProviders';
import { getExportSummary } from '../api/exportApi';
import ExportDialog from './ExportDialog';

vi.mock('../api/exportApi', async (importOriginal) => ({ ...(await importOriginal()), getExportSummary: vi.fn() }));

function renderDialog() {
  const onClose = vi.fn();
  renderWithProviders(<ExportDialog projectId={4} onClose={onClose} />);
  return onClose;
}

const yoloLink = () => screen.getByRole('link', { name: 'Download YOLO zip' });
const cocoLink = () => screen.getByRole('link', { name: 'Download COCO JSON' });

describe('ExportDialog', () => {
  beforeEach(() => {
    getExportSummary.mockReset().mockImplementation((_, { onlyReviewed }) => Promise.resolve(
      onlyReviewed ? { images: 0, boxes: 0, train: 0, val: 0 } : { images: 142, boxes: 1034, train: 128, val: 14 },
    ));
  });

  it("has today's options: flagged images left out, all labelled images (not only approved)", () => {
    renderDialog();
    expect(screen.getByRole('dialog', { name: 'Export labels' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /Approved images only/ })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: /Leave out 🚩 flagged images/ })).toBeChecked();
  });

  it('says what will be exported', async () => {
    renderDialog();
    expect(await screen.findByText('142 images (128 train / 14 val) · 1034 boxes')).toBeInTheDocument();
    expect(getExportSummary).toHaveBeenCalledWith(4, { onlyReviewed: false, skipFlagged: true });
  });

  it('downloads each format straight from the API with the chosen options', async () => {
    renderDialog();
    await screen.findByText(/142 images/);
    expect(yoloLink()).toHaveAttribute('href', '/api/projects/4/exports/yolo?onlyReviewed=false&skipFlagged=true');
    await userEvent.click(screen.getByRole('checkbox', { name: /Leave out 🚩 flagged images/ }));
    await waitFor(() => expect(cocoLink())
      .toHaveAttribute('href', '/api/projects/4/exports/coco?onlyReviewed=false&skipFlagged=false'));
    expect(getExportSummary).toHaveBeenLastCalledWith(4, { onlyReviewed: false, skipFlagged: false });
  });

  it('with nothing to export, says so and offers no download', async () => {
    renderDialog();
    await screen.findByText(/142 images/);
    await userEvent.click(screen.getByRole('checkbox', { name: /Approved images only/ }));
    expect(await screen.findByText('No labelled images match these options.')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Download YOLO zip' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Download YOLO zip' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Download COCO JSON' })).toBeDisabled();
  });

  it('shows the error when counting fails', async () => {
    getExportSummary.mockReset().mockRejectedValue(new ApiError({ status: 404, code: 'PROJECT_NOT_FOUND', detail: 'Project 4 not found.' }));
    renderDialog();
    expect(await screen.findByRole('alert')).toHaveTextContent('Project 4 not found.');
  });

  it('Close closes it', async () => {
    const onClose = renderDialog();
    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalled();
  });
});
