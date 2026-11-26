import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

/** Renders UI inside a fresh Query client (no retries) and a router. `routes` adds other pages ({ path: element }),
 * e.g. to check where a link or button goes. */
export function renderWithProviders(ui, { route = '/', path = '*', routes = {} } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const result = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path={path} element={ui} />
          {Object.entries(routes).map(([p, element]) => <Route key={p} path={p} element={element} />)}
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...result, client };
}
