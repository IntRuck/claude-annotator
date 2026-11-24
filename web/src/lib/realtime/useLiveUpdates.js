import { useEffect, useEffectEvent, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { API_BASE } from '@/config/env';
import { queryKeys } from '@/lib/queryKeys';

const REOPEN_MS = 5000;

/**
 * One SSE stream per project (GET /api/projects/{id}/events). Each message `{ type, op, data }` goes to
 * `handlers[type](client, projectId, message)`, which patches the TanStack Query caches.
 *
 * Catch-up: every time the stream (re)opens, and on a `resync` message, the project's data is refetched,
 * because changes made while it was away were missed. The browser reconnects by itself after a dropped
 * connection; if the server refused the stream, a new one is opened after a pause.
 *
 * Returns 'connecting' | 'live' | 'offline'.
 */
export function useLiveUpdates(projectId, handlers) {
  const client = useQueryClient();
  const supported = typeof EventSource !== 'undefined';
  const [status, setStatus] = useState('connecting');
  const [shownProject, setShownProject] = useState(projectId);
  if (shownProject !== projectId) {
    setShownProject(projectId);
    setStatus('connecting');
  }

  const catchUp = useEffectEvent(() => {
    client.invalidateQueries({ queryKey: queryKeys.project(projectId) });
    client.invalidateQueries({ queryKey: ['images'] }); // boxes of any open image
    client.invalidateQueries({ queryKey: queryKeys.engines() });
  });

  const onMessage = useEffectEvent((event) => {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch {
      return;
    }
    if (message.type === 'resync') catchUp();
    else handlers[message.type]?.(client, projectId, message);
  });

  useEffect(() => {
    if (!supported) return undefined;
    let source;
    let reopen;
    const open = () => {
      source = new EventSource(`${API_BASE}/projects/${projectId}/events`);
      source.onopen = () => {
        setStatus('live');
        catchUp();
      };
      source.onmessage = (event) => onMessage(event);
      source.onerror = () => {
        setStatus('offline');
        if (source.readyState === EventSource.CLOSED) reopen = setTimeout(open, REOPEN_MS);
      };
    };
    open();
    return () => {
      clearTimeout(reopen);
      source.close();
    };
  }, [projectId, supported]);

  return supported ? status : 'offline';
}
