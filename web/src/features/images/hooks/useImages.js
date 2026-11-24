import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import { listImages, setFlag, uploadImages } from '../api/imagesApi';

export function useImages(projectId, filter) {
  return useQuery({ queryKey: queryKeys.images(projectId, filter), queryFn: () => listImages(projectId, filter) });
}

export function useUploadImages(projectId) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (files) => uploadImages(projectId, files),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.imagesOf(projectId) }),
  });
}

export function useSetFlag(projectId) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ imageId, ...flag }) => setFlag(imageId, flag),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.imagesOf(projectId) }),
  });
}
