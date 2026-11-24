import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiFetch } from '@/lib/apiClient';
import { getJobSummary, queueJobs, stopJobs } from './jobsApi';

vi.mock('@/lib/apiClient', () => ({ apiFetch: vi.fn() }));

describe('jobsApi', () => {
  beforeEach(() => {
    apiFetch.mockReset().mockResolvedValue({});
  });

  it('queues AI work for a target with an engine and its options', async () => {
    const body = { target: 'unlabeled', engine: 'gemini', options: { model: 'gemini-x', extra: '' } };
    await queueJobs(4, body);
    expect(apiFetch).toHaveBeenCalledWith('/projects/4/jobs', { method: 'POST', body });
  });

  it('stops the waiting work of a project', async () => {
    await stopJobs(4);
    expect(apiFetch).toHaveBeenCalledWith('/projects/4/jobs/stop', { method: 'POST' });
  });

  it('reads the job summary', async () => {
    await getJobSummary(4);
    expect(apiFetch).toHaveBeenCalledWith('/projects/4/jobs/summary');
  });
});
