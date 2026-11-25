import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import { getHealth } from '../api/healthApi';

/** The health report, loaded each time the dialog opens. While a new warn-below number loads, the last report
 * stays on screen. */
export function useHealth(projectId, low) {
  return useQuery({
    queryKey: queryKeys.health(projectId, low),
    queryFn: () => getHealth(projectId, low),
    placeholderData: keepPreviousData,
  });
}
