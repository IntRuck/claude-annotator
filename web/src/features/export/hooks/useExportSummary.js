import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import { getExportSummary } from '../api/exportApi';

/** Counted each time the dialog opens or an option changes; the last count stays on screen while a new one loads. */
export function useExportSummary(projectId, options) {
  return useQuery({
    queryKey: queryKeys.exportSummary(projectId, options),
    queryFn: () => getExportSummary(projectId, options),
    placeholderData: keepPreviousData,
  });
}
