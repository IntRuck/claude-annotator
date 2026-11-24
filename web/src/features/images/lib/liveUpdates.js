import { queryKeys } from '@/lib/queryKeys';

/** Whether an image belongs in the list for a filter (same rule as the API's `filter`). */
export function matchesFilter(image, filter) {
  if (filter === 'all') return true;
  if (filter === 'flagged') return image.flagged;
  return image.status === filter;
}

function countsAfter(counts, before, after) {
  const next = { ...counts };
  const move = (key, by) => { if (key in next) next[key] += by; };
  if (before.status !== after.status) {
    move(before.status, -1);
    move(after.status, 1);
  }
  if (before.flagged !== after.flagged) move('flagged', after.flagged ? 1 : -1);
  return next;
}

/**
 * Live update for images (SSE `{ type: 'images', op, data }`): patch every cached image list of the project.
 * - update: the image is replaced where it is listed and the counts follow its status and flag. A list it
 *   newly belongs in is refetched. A list it no longer matches keeps it until the next refetch, so the image
 *   you are working on doesn't vanish from under you.
 *   A newer version also refetches its boxes (the editor decides whether to load them).
 * - insert / delete: the lists are refetched. Uploads send many at once, so a refetch already running is
 *   reused rather than restarted for each one.
 */
export function applyImageMessage(client, projectId, { op, data }) {
  const refetchLists = () => client.invalidateQueries({ queryKey: queryKeys.imagesOf(projectId) }, { cancelRefetch: false });
  if (op !== 'update') {
    refetchLists();
    return;
  }

  const boxes = client.getQueryData(queryKeys.boxes(data.id));
  if (boxes && boxes.updatedAt !== data.updatedAt) {
    client.invalidateQueries({ queryKey: queryKeys.boxes(data.id), exact: true });
  }

  const lists = client.getQueriesData({ queryKey: queryKeys.imagesOf(projectId) });
  const before = lists.map(([, list]) => list?.items.find((i) => i.id === data.id)).find(Boolean);
  if (!before) {
    refetchLists(); // not in any loaded list: its old status, so the right counts, are unknown
    return;
  }
  for (const [key, list] of lists) {
    if (!list) continue;
    const filter = key[3];
    const listed = list.items.some((i) => i.id === data.id);
    if (!listed && matchesFilter(data, filter)) {
      client.invalidateQueries({ queryKey: key, exact: true });
      continue;
    }
    client.setQueryData(key, {
      items: listed ? list.items.map((i) => (i.id === data.id ? data : i)) : list.items,
      counts: countsAfter(list.counts, before, data),
    });
  }
}
