import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { queryKeys } from '@/lib/queryKeys';
import { applyClassMessage } from './liveUpdates';

const cls = (index, name, extra = {}) => ({ index, name, detectorPrompt: '', description: '', ...extra });

function setup() {
  const client = new QueryClient();
  client.setQueryData(queryKeys.classes(4), [cls(0, 'can'), cls(1, 'jar')]);
  return client;
}

const classes = (client) => client.getQueryData(queryKeys.classes(4));

describe('applyClassMessage', () => {
  it('a renamed class replaces the one with its index', () => {
    const client = setup();
    applyClassMessage(client, 4, { type: 'classes', op: 'update', data: cls(1, 'glass_jar', { description: 'clear' }) });
    expect(classes(client)).toEqual([cls(0, 'can'), cls(1, 'glass_jar', { description: 'clear' })]);
  });

  it('a new class is added in index order', () => {
    const client = setup();
    applyClassMessage(client, 4, { type: 'classes', op: 'insert', data: cls(2, 'bottle') });
    expect(classes(client).map((c) => c.index)).toEqual([0, 1, 2]);
  });

  it('a deleted class is removed', () => {
    const client = setup();
    applyClassMessage(client, 4, { type: 'classes', op: 'delete', data: { index: 0 } });
    expect(classes(client)).toEqual([cls(1, 'jar')]);
  });

  it('does nothing when the class list is not loaded yet', () => {
    const client = new QueryClient();
    applyClassMessage(client, 4, { type: 'classes', op: 'insert', data: cls(0, 'can') });
    expect(classes(client)).toBeUndefined();
  });
});
