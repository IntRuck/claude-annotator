import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import { getEngineStatus, getJobSummary, queueJobs, resumeWorker, stopJobs } from '../api/jobsApi';

/** What the AI is doing for this project. Kept current by live updates; no polling. */
export function useJobSummary(projectId) {
  return useQuery({ queryKey: queryKeys.jobs(projectId), queryFn: () => getJobSummary(projectId) });
}

function useRefreshSummary(projectId) {
  const client = useQueryClient();
  // Live updates usually beat this; it covers a moment without a live connection.
  return () => client.invalidateQueries({ queryKey: queryKeys.jobs(projectId) });
}

export function useQueueJobs(projectId) {
  const refresh = useRefreshSummary(projectId);
  return useMutation({ mutationFn: (body) => queueJobs(projectId, body), onSuccess: refresh });
}

export function useStopJobs(projectId) {
  const refresh = useRefreshSummary(projectId);
  return useMutation({ mutationFn: () => stopJobs(projectId), onSuccess: refresh });
}

/** Worker heartbeat and engine pauses. Kept current by live updates; no polling. */
export function useEngineStatus() {
  return useQuery({ queryKey: queryKeys.engines(), queryFn: getEngineStatus });
}

export function useResumeWorker() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => resumeWorker(),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.engines() }),
  });
}
