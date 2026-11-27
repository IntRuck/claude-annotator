/** Every TanStack Query key in one place, so live updates and mutations patch the same caches. */
export const queryKeys = {
  projects: () => ['projects'],
  projectSummaries: () => ['project-summaries'], // not under ['projects', ...], so a project id never matches it
  project: (projectId) => ['projects', projectId],
  classes: (projectId) => ['projects', projectId, 'classes'],
  imagesOf: (projectId) => ['projects', projectId, 'images'],
  images: (projectId, filter) => ['projects', projectId, 'images', filter],
  boxes: (imageId) => ['images', imageId, 'boxes'],
  jobs: (projectId) => ['projects', projectId, 'jobs'],
  activity: (projectId) => ['projects', projectId, 'activity'],
  health: (projectId, low) => ['projects', projectId, 'health', low],
  exportSummary: (projectId, { onlyReviewed, skipFlagged, shape = 'boxes' }) =>
    ['projects', projectId, 'exports', { onlyReviewed, skipFlagged, shape }],
  engines: () => ['engines'],
};
