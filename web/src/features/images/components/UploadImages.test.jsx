import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/apiClient';
import { renderWithProviders } from '@/test/renderWithProviders';
import { uploadImages } from '../api/imagesApi';
import UploadImages from './UploadImages';

vi.mock('../api/imagesApi', () => ({ uploadImages: vi.fn(), listImages: vi.fn(), thumbUrl: vi.fn(), fileUrl: vi.fn() }));

describe('UploadImages', () => {
  beforeEach(() => {
    uploadImages.mockReset();
  });

  it('uploads the chosen files and reports what was added and skipped', async () => {
    uploadImages.mockResolvedValue({
      added: [{ id: 1, fileName: 'a.jpg' }, { id: 2, fileName: 'b.jpg' }],
      skipped: [{ fileName: 'notes.txt', reason: 'not a supported image type (jpg, jpeg, png, bmp, webp)' }],
    });
    renderWithProviders(<UploadImages projectId={4} />);
    const files = [new File(['a'], 'a.jpg', { type: 'image/jpeg' }), new File(['b'], 'b.jpg', { type: 'image/jpeg' })];

    await userEvent.upload(screen.getByLabelText('Upload images'), files);

    expect(uploadImages).toHaveBeenCalledWith(4, files);
    expect(await screen.findByText(/Added 2 · skipped 1/)).toBeInTheDocument();
    expect(screen.getByText(/notes\.txt: not a supported image type/)).toBeInTheDocument();
  });

  it('shows the server message when the upload fails', async () => {
    uploadImages.mockRejectedValue(new ApiError({ status: 502, code: 'STORAGE_UNAVAILABLE', detail: "Couldn't save a.jpg to storage" }));
    renderWithProviders(<UploadImages projectId={4} />);

    await userEvent.upload(screen.getByLabelText('Upload images'), [new File(['a'], 'a.jpg', { type: 'image/jpeg' })]);

    expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't save a.jpg to storage");
  });
});
