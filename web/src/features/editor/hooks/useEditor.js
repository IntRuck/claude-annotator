import { useReducer, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import { getBoxes, saveBoxes } from '../api/labelsApi';
import { editorReducer, initialEditor } from '../lib/history';

/**
 * Editor state for one image: its boxes with undo/redo, and saving with the save-conflict check.
 * `version` is the updatedAt the boxes were loaded or last saved at; it goes with every save.
 */
export function useEditor(image) {
  const client = useQueryClient();
  const imageId = image?.id ?? null;
  const [state, dispatch] = useReducer(editorReducer, initialEditor);
  const [conflict, setConflict] = useState(false);
  const [version, setVersion] = useState(null);
  const [shownImage, setShownImage] = useState(imageId);
  const [seenData, setSeenData] = useState(null);

  const query = useQuery({
    queryKey: queryKeys.boxes(imageId),
    queryFn: () => getBoxes(imageId),
    enabled: imageId !== null,
  });
  const mutation = useMutation({ mutationFn: (body) => saveBoxes(imageId, body) });

  const load = (data) => {
    setVersion(data.updatedAt);
    setConflict(false);
    dispatch({ type: 'load', boxes: data.boxes });
  };

  // Adjust state while rendering (React's recommended way to react to a changed prop or new data).
  let dirty = state.dirty;
  if (shownImage !== imageId) {
    setShownImage(imageId);
    setConflict(false);
    dispatch({ type: 'load', boxes: [] });
    dirty = false; // the edits belonged to the previous image
  }
  // New boxes arrive on first load, on reload, and live when someone else (or the AI) saves this image.
  // While our own save is on its way, wait: what arrives then is usually that save.
  if (query.data && query.data !== seenData && !mutation.isPending) {
    setSeenData(query.data);
    // Data we wrote ourselves after a save has our version already, so undo history survives the save.
    if (query.data.updatedAt !== version) {
      if (dirty) {
        setConflict(true); // keep the unsaved edits; Reload brings the newer boxes
      } else {
        load(query.data);
      }
    }
  }

  const save = async (status) => {
    try {
      const result = await mutation.mutateAsync({ boxes: state.boxes, status, expectedUpdatedAt: version });
      setVersion(result.image.updatedAt);
      client.setQueryData(queryKeys.boxes(imageId), { boxes: result.boxes, updatedAt: result.image.updatedAt });
      dispatch({ type: 'saved', boxes: result.boxes });
      client.invalidateQueries({ queryKey: queryKeys.imagesOf(image.projectId) });
      return result;
    } catch (error) {
      if (error?.code === 'STALE_IMAGE') setConflict(true);
      throw error;
    }
  };

  const saveIfDirty = () => (state.dirty ? save('edited') : Promise.resolve(null));

  // Load what's saved now, even if a live update already put it in the cache while we kept our edits.
  const reload = async () => {
    mutation.reset();
    const result = await query.refetch();
    if (result.isSuccess) load(result.data);
  };

  return {
    state, dispatch, save, saveIfDirty, reload, conflict,
    loading: query.isPending && imageId !== null,
    saving: mutation.isPending,
    error: conflict ? null : (mutation.error || query.error),
  };
}
