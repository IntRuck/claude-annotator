import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/apiClient';
import { renderWithProviders } from '@/test/renderWithProviders';
import { addClass, listClasses, updateClass } from '../api/classesApi';
import SkuManager from './SkuManager';

vi.mock('../api/classesApi', () => ({ listClasses: vi.fn(), addClass: vi.fn(), updateClass: vi.fn() }));

const CAN = { index: 0, name: 'can', detectorPrompt: 'metal can', description: 'Silver tin' };
const BOTTLE = { index: 1, name: 'bottle', detectorPrompt: '', description: '' };

function rowOf(index) {
  return screen.getByRole('row', { name: `SKU ${index}` });
}

describe('SkuManager', () => {
  beforeEach(() => {
    listClasses.mockReset().mockResolvedValue([CAN, BOTTLE]);
    addClass.mockReset();
    updateClass.mockReset();
  });

  it('shows each SKU with its ID, name, detector prompt and description', async () => {
    renderWithProviders(<SkuManager projectId={5} onClose={() => {}} />);
    await screen.findByDisplayValue('can');
    const row = within(rowOf(0));
    expect(row.getByText('0')).toBeInTheDocument();
    expect(row.getByLabelText('Name')).toHaveValue('can');
    expect(row.getByLabelText('Detector prompt')).toHaveValue('metal can');
    expect(row.getByLabelText('Description')).toHaveValue('Silver tin');
  });

  it('saves a changed field when you leave it', async () => {
    updateClass.mockResolvedValue({ ...CAN, description: 'Silver tin, red lid' });
    renderWithProviders(<SkuManager projectId={5} onClose={() => {}} />);
    await screen.findByDisplayValue('Silver tin');
    const description = within(rowOf(0)).getByLabelText('Description');

    await userEvent.type(description, ', red lid');
    await userEvent.tab();

    expect(updateClass).toHaveBeenCalledWith(5, 0, { description: 'Silver tin, red lid' });
  });

  it('does not save a field that did not change', async () => {
    renderWithProviders(<SkuManager projectId={5} onClose={() => {}} />);
    await screen.findByDisplayValue('can');
    await userEvent.click(within(rowOf(0)).getByLabelText('Name'));
    await userEvent.tab();
    expect(updateClass).not.toHaveBeenCalled();
  });

  it('puts a blank name back instead of saving it', async () => {
    renderWithProviders(<SkuManager projectId={5} onClose={() => {}} />);
    const name = await screen.findByDisplayValue('can');
    await userEvent.clear(name);
    await userEvent.tab();
    expect(updateClass).not.toHaveBeenCalled();
    expect(name).toHaveValue('can');
  });

  it('adds a new SKU at the end and clears the form', async () => {
    addClass.mockResolvedValue({ index: 2, name: 'tuna_400g', detectorPrompt: 'red tin', description: '' });
    renderWithProviders(<SkuManager projectId={5} onClose={() => {}} />);
    await screen.findByDisplayValue('can');

    await userEvent.type(screen.getByLabelText('New SKU name'), 'tuna 400g');
    await userEvent.type(screen.getByLabelText('New SKU detector prompt'), 'red tin');
    await userEvent.click(screen.getByRole('button', { name: 'Add SKU' }));

    expect(addClass).toHaveBeenCalledWith(5, { name: 'tuna 400g', detectorPrompt: 'red tin', description: '' });
    await waitFor(() => expect(screen.getByLabelText('New SKU name')).toHaveValue(''));
  });

  it('shows the server message when a name is taken', async () => {
    addClass.mockRejectedValue(new ApiError({ status: 409, code: 'CLASS_NAME_TAKEN', detail: 'A class called "can" already exists in this project.' }));
    renderWithProviders(<SkuManager projectId={5} onClose={() => {}} />);
    await screen.findByDisplayValue('can');

    await userEvent.type(screen.getByLabelText('New SKU name'), 'Can');
    await userEvent.click(screen.getByRole('button', { name: 'Add SKU' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('already exists');
  });

  it('closes with the Close button', async () => {
    const onClose = vi.fn();
    renderWithProviders(<SkuManager projectId={5} onClose={onClose} />);
    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalled();
  });
});
