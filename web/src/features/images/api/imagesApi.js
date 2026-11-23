import { API_BASE } from '@/config/env';
import { apiFetch } from '@/lib/apiClient';

export const listImages = (projectId, filter) =>
  apiFetch(`/projects/${projectId}/images?filter=${encodeURIComponent(filter)}`);

export function uploadImages(projectId, files) {
  const form = new FormData();
  for (const file of files) form.append('files', file, file.name);
  return apiFetch(`/projects/${projectId}/images`, { method: 'POST', body: form });
}

/** The API answers these with a redirect to a short-lived signed Storage link. */
export const thumbUrl = (imageId) => `${API_BASE}/images/${imageId}/thumb`;
export const fileUrl = (imageId) => `${API_BASE}/images/${imageId}/file`;
