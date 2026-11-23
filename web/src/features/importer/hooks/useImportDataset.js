import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import { importDataset } from '../api/importApi';

export function useImportDataset(projectId) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (files) => importDataset(projectId, files),
    onSuccess: () => Promise.all([
      client.invalidateQueries({ queryKey: queryKeys.imagesOf(projectId) }),
      client.invalidateQueries({ queryKey: queryKeys.classes(projectId) }),
    ]),
  });
}
