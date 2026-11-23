import { apiFetch } from '@/lib/apiClient';

export const listClasses = (projectId) => apiFetch(`/projects/${projectId}/classes`);

export const addClass = (projectId, body) => apiFetch(`/projects/${projectId}/classes`, { method: 'POST', body });

/** Only the fields in `changes` are updated. The class index never changes. */
export const updateClass = (projectId, index, changes) =>
  apiFetch(`/projects/${projectId}/classes/${index}`, { method: 'PATCH', body: changes });
