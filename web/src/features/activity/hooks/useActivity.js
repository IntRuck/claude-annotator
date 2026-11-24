import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import { listActivity } from '../api/activityApi';

/** The project's recent activity. New entries arrive by live update; no polling. */
export function useActivity(projectId) {
  return useQuery({ queryKey: queryKeys.activity(projectId), queryFn: () => listActivity(projectId) });
}
