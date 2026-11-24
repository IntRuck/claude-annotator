import { queryKeys } from '@/lib/queryKeys';

export const MAX_ENTRIES = 200;

/** Live update for the activity log (SSE `{ type: 'activity', op: 'insert', data }`): newest on top. */
export function applyActivityMessage(client, projectId, { data }) {
  client.setQueryData(queryKeys.activity(projectId), (log) => {
    if (!log || log.some((e) => e.id === data.id)) return log;
    return [data, ...log].slice(0, MAX_ENTRIES);
  });
}
