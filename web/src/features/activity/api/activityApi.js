import { apiFetch } from '@/lib/apiClient';

export const listActivity = (projectId, limit = 100) => apiFetch(`/projects/${projectId}/activity?limit=${limit}`);
