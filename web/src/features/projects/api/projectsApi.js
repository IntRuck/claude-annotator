import { apiFetch } from '@/lib/apiClient';

export const listProjects = () => apiFetch('/projects');

/** Every project with its numbers (images, labelled, approved, SKUs, cover, last change), for the projects page. */
export const listProjectSummaries = () => apiFetch('/project-summaries');

export const getProject = (projectId) => apiFetch(`/projects/${projectId}`);

export const createProject = ({ name, description = '' }) =>
  apiFetch('/projects', { method: 'POST', body: { name, description } });

/** `patch`: { name?, description? }; only the fields sent change. */
export const updateProject = (projectId, patch) => apiFetch(`/projects/${projectId}`, { method: 'PATCH', body: patch });

/** Deletes the project with all its photos, labels and SKUs. */
export const deleteProject = (projectId) => apiFetch(`/projects/${projectId}`, { method: 'DELETE' });
