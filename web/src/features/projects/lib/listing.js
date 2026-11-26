/** Search and sort for the projects page. Runs in the browser: the list is small. */
export const SORTS = [
  ['changed', 'Last changed'],
  ['name', 'Name A–Z'],
  ['newest', 'Newest'],
];

const BY = {
  changed: (a, b) => b.lastChangedAt.localeCompare(a.lastChangedAt),
  name: (a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }),
  newest: (a, b) => b.createdAt.localeCompare(a.createdAt),
};

/** A new list: projects whose name or description has `query` (ignoring capitals), in `sort` order. */
export function arrangeProjects(projects, { query = '', sort = 'changed' } = {}) {
  const q = query.trim().toLowerCase();
  const hits = q
    ? projects.filter((p) => p.name.toLowerCase().includes(q) || (p.description ?? '').toLowerCase().includes(q))
    : [...projects];
  return hits.sort(BY[sort] ?? BY.changed);
}
