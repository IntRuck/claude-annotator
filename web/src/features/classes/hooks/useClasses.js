import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import { addClass, listClasses, updateClass } from '../api/classesApi';

export function useClasses(projectId) {
  return useQuery({ queryKey: queryKeys.classes(projectId), queryFn: () => listClasses(projectId) });
}

function useRefreshClasses(projectId) {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: queryKeys.classes(projectId) });
}

export function useAddClass(projectId) {
  const refresh = useRefreshClasses(projectId);
  return useMutation({ mutationFn: (body) => addClass(projectId, body), onSuccess: refresh });
}

export function useUpdateClass(projectId) {
  const refresh = useRefreshClasses(projectId);
  return useMutation({ mutationFn: ({ index, changes }) => updateClass(projectId, index, changes), onSuccess: refresh });
}
