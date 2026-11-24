import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { queryKeys } from '@/lib/queryKeys';
import { applyWorkerMessage } from './liveUpdates';
import { OFFLINE_AFTER_MS, isWorkerOnline } from './workerStatus';

const NOW = Date.parse('2026-11-24T10:00:00Z');

describe('isWorkerOnline', () => {
  it('is online while the last heartbeat is recent', () => {
    expect(OFFLINE_AFTER_MS).toBe(45000);
    expect(isWorkerOnline({ lastSeenAt: '2026-11-24T09:59:20Z' }, NOW)).toBe(true);
    expect(isWorkerOnline({ lastSeenAt: '2026-11-24T09:59:10Z' }, NOW)).toBe(false);
  });

  it('is offline when no worker ever reported, and unknown before the status loads', () => {
    expect(isWorkerOnline({ lastSeenAt: null }, NOW)).toBe(false);
    expect(isWorkerOnline(undefined, NOW)).toBeNull();
  });
});

describe('applyWorkerMessage', () => {
  it('the engine status from the server replaces the cached one', () => {
    const client = new QueryClient();
    const data = { workerOnline: true, lastSeenAt: 'T', engines: {}, paused: [] };
    applyWorkerMessage(client, 4, { type: 'worker', op: 'status', data });
    expect(client.getQueryData(queryKeys.engines())).toEqual(data);
  });
});
