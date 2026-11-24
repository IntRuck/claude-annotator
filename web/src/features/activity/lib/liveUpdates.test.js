import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { queryKeys } from '@/lib/queryKeys';
import { MAX_ENTRIES, applyActivityMessage } from './liveUpdates';

const entry = (id, message = `line ${id}`) => ({ id, level: 'info', message, jobId: null, imageId: null, createdAt: 'T' });

describe('applyActivityMessage', () => {
  it('a new entry goes on top of the cached log', () => {
    const client = new QueryClient();
    client.setQueryData(queryKeys.activity(4), [entry(2), entry(1)]);

    applyActivityMessage(client, 4, { type: 'activity', op: 'insert', data: entry(3) });

    expect(client.getQueryData(queryKeys.activity(4)).map((e) => e.id)).toEqual([3, 2, 1]);
  });

  it('an entry already shown (it came with a refetch) is not added twice', () => {
    const client = new QueryClient();
    client.setQueryData(queryKeys.activity(4), [entry(3), entry(2)]);
    applyActivityMessage(client, 4, { type: 'activity', op: 'insert', data: entry(3) });
    expect(client.getQueryData(queryKeys.activity(4))).toHaveLength(2);
  });

  it('keeps the log from growing forever', () => {
    const client = new QueryClient();
    client.setQueryData(queryKeys.activity(4), Array.from({ length: MAX_ENTRIES }, (_, i) => entry(MAX_ENTRIES - i)));
    applyActivityMessage(client, 4, { type: 'activity', op: 'insert', data: entry(MAX_ENTRIES + 1) });
    const log = client.getQueryData(queryKeys.activity(4));
    expect(log).toHaveLength(MAX_ENTRIES);
    expect(log[0].id).toBe(MAX_ENTRIES + 1);
  });

  it('does nothing before the log is loaded', () => {
    const client = new QueryClient();
    applyActivityMessage(client, 4, { type: 'activity', op: 'insert', data: entry(1) });
    expect(client.getQueryData(queryKeys.activity(4))).toBeUndefined();
  });
});
