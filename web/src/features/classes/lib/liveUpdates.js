import { queryKeys } from '@/lib/queryKeys';

/** Live update for classes (SSE `{ type: 'classes', op, data }`): patch the project's class list in place. */
export function applyClassMessage(client, projectId, { op, data }) {
  client.setQueryData(queryKeys.classes(projectId), (list) => {
    if (!list) return list;
    const others = list.filter((c) => c.index !== data.index);
    if (op === 'delete') return others;
    return [...others, data].sort((a, b) => a.index - b.index);
  });
}
