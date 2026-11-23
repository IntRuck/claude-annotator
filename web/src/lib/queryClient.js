import { QueryClient } from '@tanstack/react-query';

/** Shared TanStack Query client. Live updates (SSE) patch its caches, so no polling is set here. */
export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: 1, refetchOnWindowFocus: false },
    },
  });
}
