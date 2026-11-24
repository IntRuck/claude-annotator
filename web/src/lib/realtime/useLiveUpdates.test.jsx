import { act, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { queryKeys } from '@/lib/queryKeys';
import { FakeEventSource } from '@/test/fakeEventSource';
import { useLiveUpdates } from './useLiveUpdates';

const latest = () => FakeEventSource.latest();

function setup(projectId = 4, handlers = {}) {
  const client = new QueryClient();
  const invalidate = vi.spyOn(client, 'invalidateQueries');
  const wrapper = ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const hook = renderHook(({ id }) => useLiveUpdates(id, handlers), { wrapper, initialProps: { id: projectId } });
  return { ...hook, client, invalidate };
}

describe('useLiveUpdates', () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal('EventSource', FakeEventSource);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('opens the project\'s event stream and says when it is live', () => {
    const { result } = setup();
    expect(latest().url).toBe('/api/projects/4/events');
    expect(result.current).toBe('connecting');

    act(() => latest().open());
    expect(result.current).toBe('live');
  });

  it('refetches the project\'s data every time it (re)connects, to catch up on missed changes', () => {
    const { invalidate } = setup();
    act(() => latest().open());
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.project(4) });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['images'] });

    invalidate.mockClear();
    act(() => latest().fail());
    act(() => latest().open());
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.project(4) });
  });

  it('hands each message to the handler for its type', () => {
    const images = vi.fn();
    const { client } = setup(4, { images });
    act(() => latest().open());
    const message = { type: 'images', op: 'update', data: { id: 1 } };

    act(() => latest().emit(message));

    expect(images).toHaveBeenCalledWith(client, 4, message);
  });

  it('a resync message refetches everything, like a reconnect', () => {
    const { invalidate } = setup();
    act(() => latest().open());
    invalidate.mockClear();

    act(() => latest().emit({ type: 'resync' }));

    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.project(4) });
  });

  it('ignores messages it has no handler for, and broken ones', () => {
    setup(4, {});
    act(() => latest().open());
    expect(() => act(() => {
      latest().emit({ type: 'robots', op: 'update', data: {} });
      latest().emit('not json');
    })).not.toThrow();
  });

  it('shows offline while the browser reconnects by itself', () => {
    const { result } = setup();
    act(() => latest().open());

    act(() => latest().fail());

    expect(result.current).toBe('offline');
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it('opens a new stream after a pause when the server closed it for good', () => {
    vi.useFakeTimers();
    setup();
    act(() => latest().fail(true));
    expect(FakeEventSource.instances).toHaveLength(1);

    act(() => vi.advanceTimersByTime(5000));

    expect(FakeEventSource.instances).toHaveLength(2);
  });

  it('closes the stream when the page goes away', () => {
    vi.useFakeTimers();
    const { unmount } = setup();
    const source = latest();
    act(() => source.fail(true));

    unmount();
    act(() => vi.advanceTimersByTime(5000));

    expect(source.closed).toBe(true);
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it('switches stream when the project changes', () => {
    const { rerender, result } = setup();
    act(() => latest().open());
    const first = latest();

    rerender({ id: 7 });

    expect(first.closed).toBe(true);
    expect(latest().url).toBe('/api/projects/7/events');
    expect(result.current).toBe('connecting');
  });

  it('is simply offline in a browser without EventSource', () => {
    vi.stubGlobal('EventSource', undefined);
    const { result } = setup();
    expect(result.current).toBe('offline');
  });
});
