import { useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import { listImages, setFlag, uploadImages } from '../api/imagesApi';
import { CUSTOM, apiFilter, keepOnly } from '../lib/filters';

const NONE = [];

/** Images of a filter. With the CUSTOM filter, only `pickedIds` out of all images. */
export function useImages(projectId, filter, pickedIds = NONE) {
  const loaded = apiFilter(filter);
  const select = useCallback((data) => keepOnly(data, pickedIds), [pickedIds]);
  return useQuery({
    queryKey: queryKeys.images(projectId, loaded),
    queryFn: () => listImages(projectId, loaded),
    select: filter === CUSTOM ? select : undefined,
  });
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
