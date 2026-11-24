import { apiFetch } from '@/lib/apiClient';

/** Queue AI work: `{ target: 'image' | 'unlabeled' | 'errors' | 'all', imageId?, engine, options }`. */
export const queueJobs = (projectId, body) => apiFetch(`/projects/${projectId}/jobs`, { method: 'POST', body });

/** Cancel the waiting images; the one being labelled finishes first. */
export const stopJobs = (projectId) => apiFetch(`/projects/${projectId}/jobs/stop`, { method: 'POST' });

export const getJobSummary = (projectId) => apiFetch(`/projects/${projectId}/jobs/summary`);
