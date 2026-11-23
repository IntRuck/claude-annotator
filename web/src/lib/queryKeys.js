/** Every TanStack Query key in one place, so live updates and mutations patch the same caches. */
export const queryKeys = {
  projects: () => ['projects'],
  project: (projectId) => ['projects', projectId],
  classes: (projectId) => ['projects', projectId, 'classes'],
};
