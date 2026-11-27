import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiFetch } from '@/lib/apiClient';
import { exportUrl, getExportSummary } from './exportApi';

vi.mock('@/lib/apiClient', () => ({ apiFetch: vi.fn() }));

describe('exportApi', () => {
  beforeEach(() => {
    apiFetch.mockReset().mockResolvedValue({});
  });

  it('counts what an export with these options would hold', async () => {
    await getExportSummary(4, { onlyReviewed: true, skipFlagged: false });
    expect(apiFetch).toHaveBeenCalledWith('/projects/4/exports/summary?onlyReviewed=true&skipFlagged=false');
  });

  it('builds the download link for each format, through the API', () => {
    expect(exportUrl(4, 'yolo', { onlyReviewed: false, skipFlagged: true }))
      .toBe('/api/projects/4/exports/yolo?onlyReviewed=false&skipFlagged=true');
    expect(exportUrl(4, 'coco', { onlyReviewed: true, skipFlagged: true }))
      .toBe('/api/projects/4/exports/coco?onlyReviewed=true&skipFlagged=true');
  });

  it('adds shape=outlines only for outlines, so box links stay as today', async () => {
    await getExportSummary(4, { onlyReviewed: false, skipFlagged: true, shape: 'boxes' });
    expect(apiFetch).toHaveBeenLastCalledWith('/projects/4/exports/summary?onlyReviewed=false&skipFlagged=true');
    expect(exportUrl(4, 'coco', { onlyReviewed: false, skipFlagged: true, shape: 'outlines' }))
      .toBe('/api/projects/4/exports/coco?onlyReviewed=false&skipFlagged=true&shape=outlines');
  });
});
