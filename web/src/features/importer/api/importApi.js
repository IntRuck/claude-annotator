import { apiFetch } from '@/lib/apiClient';

/** Sends a dataset folder. Each file keeps its folder path as its name, so the server can match labels to images. */
export function importDataset(projectId, files) {
  const form = new FormData();
  for (const file of files) form.append('files', file, file.webkitRelativePath || file.name);
  return apiFetch(`/projects/${projectId}/import`, { method: 'POST', body: form });
}
