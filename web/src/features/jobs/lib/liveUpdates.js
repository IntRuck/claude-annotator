import { queryKeys } from '@/lib/queryKeys';

/** Live update for jobs (SSE `{ type: 'jobs', op: 'summary', data }`): the server sends the whole summary. */
export function applyJobMessage(client, projectId, { data }) {
  client.setQueryData(queryKeys.jobs(projectId), data);
}

/** Live update for the worker (SSE `{ type: 'worker', op: 'status', data }`): heartbeats and engine pauses. */
export function applyWorkerMessage(client, projectId, { data }) {
  client.setQueryData(queryKeys.engines(), data);
}
