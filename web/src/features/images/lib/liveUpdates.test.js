import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { queryKeys } from '@/lib/queryKeys';
import { applyImageMessage } from './liveUpdates';

const img = (id, extra = {}) => ({
  id, projectId: 4, fileName: `${id}.jpg`, status: 'unlabeled', flagged: false, boxCount: 0, updatedAt: 'T1', ...extra,
});
const COUNTS = { all: 2, unlabeled: 2, auto: 0, edited: 0, reviewed: 0, flagged: 0, error: 0 };
const update = (data) => ({ type: 'images', op: 'update', data });

function setup() {
  const client = new QueryClient();
  client.setQueryData(queryKeys.images(4, 'all'), { items: [img(1), img(2)], counts: COUNTS });
  client.setQueryData(queryKeys.images(4, 'unlabeled'), { items: [img(1), img(2)], counts: COUNTS });
  client.setQueryData(queryKeys.images(4, 'auto'), { items: [], counts: COUNTS });
  client.setQueryData(queryKeys.images(9, 'all'), { items: [img(1, { projectId: 9 })], counts: COUNTS });
  return client;
}

const list = (client, filter, projectId = 4) => client.getQueryData(queryKeys.images(projectId, filter));

describe('applyImageMessage', () => {
  it('an image update replaces that image in every cached list of the project', () => {
    const client = setup();
    const changed = img(1, { status: 'auto', boxCount: 3, updatedAt: 'T2' });

    applyImageMessage(client, 4, update(changed));

    expect(list(client, 'all').items).toEqual([changed, img(2)]);
    expect(list(client, 'unlabeled').items[0]).toEqual(changed);
  });

  it('counts follow the status and the flag', () => {
    const client = setup();
    applyImageMessage(client, 4, update(img(1, { status: 'auto' })));
    applyImageMessage(client, 4, update(img(2, { flagged: true })));

    expect(list(client, 'all').counts).toEqual({ ...COUNTS, unlabeled: 1, auto: 1, flagged: 1 });
    expect(list(client, 'unlabeled').counts).toEqual(list(client, 'all').counts);
  });

  it('an image that now matches a filter it was missing from refetches that list', () => {
    const client = setup();
    const invalidate = vi.spyOn(client, 'invalidateQueries');

    applyImageMessage(client, 4, update(img(1, { status: 'auto' })));

    expect(invalidate).toHaveBeenCalledTimes(1);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.images(4, 'auto'), exact: true });
  });

  it('an image that no longer matches the filter stays in the list (so the one you are on does not vanish)', () => {
    const client = setup();
    applyImageMessage(client, 4, update(img(1, { status: 'edited' })));
    expect(list(client, 'unlabeled').items.map((i) => i.id)).toEqual([1, 2]);
  });

  it('an image missing from every cached list refetches the lists (its old status, so the counts, are unknown)', () => {
    const client = setup();
    const invalidate = vi.spyOn(client, 'invalidateQueries');

    applyImageMessage(client, 4, update(img(7, { status: 'edited' })));

    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.imagesOf(4) }, { cancelRefetch: false });
    expect(list(client, 'all').counts).toEqual(COUNTS);
  });

  it('leaves other projects alone', () => {
    const client = setup();
    applyImageMessage(client, 4, update(img(1, { status: 'auto' })));
    expect(list(client, 'all', 9).items[0].status).toBe('unlabeled');
  });

  it('a newer version refetches that image\'s boxes; the same version (our own save) does not', () => {
    const client = setup();
    client.setQueryData(queryKeys.boxes(1), { boxes: [], updatedAt: 'T1' });
    client.setQueryData(queryKeys.boxes(2), { boxes: [], updatedAt: 'T5' });
    const invalidate = vi.spyOn(client, 'invalidateQueries');

    applyImageMessage(client, 4, update(img(1, { updatedAt: 'T2' })));
    applyImageMessage(client, 4, update(img(2, { updatedAt: 'T5' })));

    expect(invalidate).toHaveBeenCalledTimes(1);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.boxes(1), exact: true });
  });

  it.each(['insert', 'delete'])('an image %s refetches the project\'s lists once a burst is over', (op) => {
    const client = setup();
    const invalidate = vi.spyOn(client, 'invalidateQueries');

    applyImageMessage(client, 4, { type: 'images', op, data: { id: 3 } });

    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.imagesOf(4) }, { cancelRefetch: false });
  });
});
