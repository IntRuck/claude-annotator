import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/apiClient';
import { renderWithProviders } from '@/test/renderWithProviders';
import { importDataset } from '../api/importApi';
import ImportDataset from './ImportDataset';

vi.mock('../api/importApi', () => ({ importDataset: vi.fn() }));

const RESULT = {
  added: 3, skipped: [{ fileName: 'a.jpg', reason: 'already in this project' }], labelled: 2, boxes: 5,
  classesCreated: ['can', 'bottle'], placeholderClasses: [], keptExistingClasses: false,
  labelsWithoutImage: [], badLabelLines: 0, statesApplied: 2, ignoredFiles: ['readme.md'], warnings: [],
};

async function pickFolder() {
  const files = [new File(['x'], 'b.jpg'), new File(['y'], 'b.txt')];
  await userEvent.upload(screen.getByLabelText('Choose dataset folder'), files);
  return files;
}

describe('ImportDataset', () => {
  beforeEach(() => {
    importDataset.mockReset();
  });

  it('imports the chosen folder and says what happened', async () => {
    importDataset.mockResolvedValue(RESULT);
    renderWithProviders(<ImportDataset projectId={4} onClose={() => {}} />);

    const files = await pickFolder();

    expect(importDataset).toHaveBeenCalledWith(4, files);
    expect(await screen.findByText('Added 3 images · 2 labelled with 5 boxes')).toBeInTheDocument();
    expect(screen.getByText('Classes from the folder: can, bottle')).toBeInTheDocument();
    expect(screen.getByText('Statuses and flags brought over for 2 images.')).toBeInTheDocument();
    expect(screen.getByText('a.jpg: already in this project')).toBeInTheDocument();
    expect(screen.getByText('1 other file ignored.')).toBeInTheDocument();
  });

  it('explains placeholder classes, kept classes, unmatched labels and warnings', async () => {
    importDataset.mockResolvedValue({
      ...RESULT, classesCreated: [], keptExistingClasses: true, placeholderClasses: ['class_3'],
      labelsWithoutImage: ['ghost.txt'], badLabelLines: 2, ignoredFiles: [],
      warnings: ["Couldn't read _annot_state.json, so statuses and flags weren't imported."],
    });
    renderWithProviders(<ImportDataset projectId={4} onClose={() => {}} />);

    await pickFolder();

    expect(await screen.findByText(/Kept this project's classes/)).toBeInTheDocument();
    expect(screen.getByText(/placeholder classes: class_3/)).toBeInTheDocument();
    expect(screen.getByText(/No image for these label files: ghost\.txt/)).toBeInTheDocument();
    expect(screen.getByText('2 label lines could not be read and were skipped.')).toBeInTheDocument();
    expect(screen.getByText(/Couldn't read _annot_state\.json/)).toBeInTheDocument();
  });

  it('shows the server message when the import fails', async () => {
    importDataset.mockRejectedValue(new ApiError({ status: 502, code: 'STORAGE_UNAVAILABLE', detail: "Couldn't save b.jpg to storage" }));
    renderWithProviders(<ImportDataset projectId={4} onClose={() => {}} />);

    await pickFolder();

    expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't save b.jpg to storage");
  });

  it('lets you pick a whole folder', () => {
    renderWithProviders(<ImportDataset projectId={4} onClose={() => {}} />);
    expect(screen.getByLabelText('Choose dataset folder')).toHaveAttribute('webkitdirectory');
  });
});
