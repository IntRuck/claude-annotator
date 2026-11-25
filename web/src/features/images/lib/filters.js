/** Image filters, with today's labels. The value matches the API's `filter` parameter. */
export const FILTERS = [
  { value: 'all', label: 'All images' },
  { value: 'unlabeled', label: 'Unlabeled' },
  { value: 'auto', label: 'Labeled by AI (not checked)' },
  { value: 'edited', label: 'Edited' },
  { value: 'reviewed', label: 'Approved' },
  { value: 'flagged', label: '🚩 Flagged' },
  { value: 'error', label: 'Errors' },
];

/** A set of images picked elsewhere (a health-check issue or class), shown as its own filter. */
export const CUSTOM = 'custom';

/** The API `filter` to load: a picked set is cut out of all images. */
export function apiFilter(filter) {
  return filter === CUSTOM ? 'all' : filter;
}

/** The image list with only the picked ids, in list order. Counts stay those of the whole project. */
export function keepOnly(data, ids) {
  const wanted = new Set(ids);
  return { ...data, items: data.items.filter((image) => wanted.has(image.id)) };
}
