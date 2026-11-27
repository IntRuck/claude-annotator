import { API_BASE } from '@/config/env';
import { apiFetch } from '@/lib/apiClient';

// shape=outlines is added only for outlines, so box links stay exactly as before.
const query = ({ onlyReviewed, skipFlagged, shape }) => new URLSearchParams({
  onlyReviewed: String(onlyReviewed), skipFlagged: String(skipFlagged), ...(shape === 'outlines' ? { shape } : {}),
}).toString();

/** How many images, boxes and train/val images an export with these options would hold. */
export const getExportSummary = (projectId, options) =>
  apiFetch(`/projects/${projectId}/exports/summary?${query(options)}`);

/** Direct download link ('yolo' zip or 'coco' JSON): the API builds the file and the browser saves it. */
export const exportUrl = (projectId, format, options) =>
  `${API_BASE}/projects/${projectId}/exports/${format}?${query(options)}`;
