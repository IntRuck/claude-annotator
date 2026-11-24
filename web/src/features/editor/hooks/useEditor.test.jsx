import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/apiClient';
import { getBoxes, saveBoxes } from '../api/labelsApi';
import { useEditor } from './useEditor';

vi.mock('../api/labelsApi', () => ({ getBoxes: vi.fn(), saveBoxes: vi.fn() }));

const BOX = { cls: 0, x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5, source: 'ai', conf: 0.9 };
const IMAGE = { id: 5, projectId: 1, fileName: 'a.jpg', width: 200, height: 100, status: 'auto' };

function setup(image = IMAGE) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const wrapper = ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return renderHook(({ img }) => useEditor(img), { wrapper, initialProps: { img: image } });
}

describe('useEditor', () => {
  beforeEach(() => {
    getBoxes.mockReset().mockResolvedValue({ boxes: [BOX], updatedAt: 'T1' });
    saveBoxes.mockReset();
  });

  it('loads the image\'s boxes into the editor', async () => {
    const { result } = setup();
    await waitFor(() => expect(result.current.state.boxes).toEqual([BOX]));
    expect(result.current.state.dirty).toBe(false);
  });

  it('saves with the loaded version, then uses the new version for the next save', async () => {
    saveBoxes.mockResolvedValueOnce({ image: { ...IMAGE, status: 'edited', updatedAt: 'T2' }, boxes: [BOX] })
      .mockResolvedValueOnce({ image: { ...IMAGE, status: 'reviewed', updatedAt: 'T3' }, boxes: [BOX] });
    const { result } = setup();
    await waitFor(() => expect(result.current.state.boxes).toHaveLength(1));

    act(() => result.current.dispatch({ type: 'remove' }));
    await act(() => result.current.save('edited'));
    expect(saveBoxes).toHaveBeenLastCalledWith(5, { boxes: [BOX], status: 'edited', expectedUpdatedAt: 'T1' });
    await act(() => result.current.save('reviewed'));
    expect(saveBoxes).toHaveBeenLastCalledWith(5, { boxes: [BOX], status: 'reviewed', expectedUpdatedAt: 'T2' });
    expect(result.current.state.dirty).toBe(false);
  });

  it('saveIfDirty saves as edited only when there are unsaved changes', async () => {
    saveBoxes.mockResolvedValue({ image: { ...IMAGE, updatedAt: 'T2' }, boxes: [] });
    const { result } = setup();
    await waitFor(() => expect(result.current.state.boxes).toHaveLength(1));
    await act(() => result.current.saveIfDirty());
    expect(saveBoxes).not.toHaveBeenCalled();

    act(() => {
      result.current.dispatch({ type: 'select', index: 0 });
      result.current.dispatch({ type: 'remove' });
    });
    await act(() => result.current.saveIfDirty());
    expect(saveBoxes).toHaveBeenCalledWith(5, { boxes: [], status: 'edited', expectedUpdatedAt: 'T1' });
  });

  it('a newer save by someone else shows as a conflict, and reload brings their boxes', async () => {
    saveBoxes.mockRejectedValue(new ApiError({ status: 409, code: 'STALE_IMAGE', detail: 'changed since you opened it' }));
    const { result } = setup();
    await waitFor(() => expect(result.current.state.boxes).toHaveLength(1));

    await act(() => result.current.save('edited').catch(() => {}));
    expect(result.current.conflict).toBe(true);

    getBoxes.mockResolvedValue({ boxes: [], updatedAt: 'T9' });
    await act(() => result.current.reload());
    await waitFor(() => expect(result.current.state.boxes).toEqual([]));
    expect(result.current.conflict).toBe(false);
  });

  it('switching image loads the new image\'s boxes', async () => {
    const { result, rerender } = setup();
    await waitFor(() => expect(result.current.state.boxes).toHaveLength(1));
    getBoxes.mockResolvedValue({ boxes: [], updatedAt: 'T5' });
    rerender({ img: { ...IMAGE, id: 6 } });
    await waitFor(() => expect(result.current.state.boxes).toEqual([]));
    expect(getBoxes).toHaveBeenLastCalledWith(6);
  });
});
