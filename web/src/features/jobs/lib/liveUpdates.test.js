import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { queryKeys } from '@/lib/queryKeys';
import { applyJobMessage } from './liveUpdates';
import { noticeFor, statusText } from './status';

describe('applyJobMessage', () => {
  it('a job summary replaces the cached one', () => {
    const client = new QueryClient();
    const summary = { queued: 3, running: [{ id: 1, imageId: 2, fileName: 'b.jpg', engine: 'gemini', kind: 'annotate' }] };
    applyJobMessage(client, 4, { type: 'jobs', op: 'summary', data: summary });
    expect(client.getQueryData(queryKeys.jobs(4))).toEqual(summary);
  });
});

describe('statusText', () => {
  it('names the image being labelled and how many are waiting', () => {
    expect(statusText({ queued: 3, running: [{ fileName: 'b.jpg' }] })).toBe('Labeling b.jpg… · 3 waiting');
    expect(statusText({ queued: 0, running: [{ fileName: 'b.jpg' }] })).toBe('Labeling b.jpg…');
    expect(statusText({ queued: 2, running: [] })).toBe('2 waiting');
    expect(statusText({ queued: 0, running: [] })).toBe('idle');
    expect(statusText(undefined)).toBe('idle');
  });
});

describe('noticeFor', () => {
  it('says when a button found nothing to do', () => {
    expect(noticeFor({ matched: 0, queued: 0, alreadyQueued: 0 })).toBe('Nothing to label');
    expect(noticeFor({ matched: 2, queued: 0, alreadyQueued: 2 })).toBe('Already queued');
    expect(noticeFor({ matched: 2, queued: 2, alreadyQueued: 0 })).toBe('');
  });
});
