import { apiFetch } from '@/lib/apiClient';

export const listProjects = () => apiFetch('/projects');

export const getProject = (projectId) => apiFetch(`/projects/${projectId}`);

export const createProject = (name) => apiFetch('/projects', { method: 'POST', body: { name } });
