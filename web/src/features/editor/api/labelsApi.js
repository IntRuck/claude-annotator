import { apiFetch } from '@/lib/apiClient';

export const getBoxes = (imageId) => apiFetch(`/images/${imageId}/boxes`);

/** Saves the whole box set. `expectedUpdatedAt` is the version the boxes were loaded at (save-conflict check). */
export const saveBoxes = (imageId, { boxes, status, expectedUpdatedAt }) =>
  apiFetch(`/images/${imageId}/boxes`, { method: 'PUT', body: { boxes, status, expectedUpdatedAt } });
