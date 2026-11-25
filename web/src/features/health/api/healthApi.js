import { apiFetch } from '@/lib/apiClient';

/** The dataset health report; classes with fewer boxes than `low` get a "low" warning. */
export const getHealth = (projectId, low = 100) => apiFetch(`/projects/${projectId}/health?low=${low}`);
