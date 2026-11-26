# CLAUDE.md — web (React 19 + Vite)

Root rules still apply: see [../CLAUDE.md](../CLAUDE.md). Same conventions as `mr-robot-codebase/frontend_web`.

## Layout

- `src/app/` providers (`QueryProvider`) and routes
- `src/features/<name>/` domain modules, each with `api/`, `hooks/`, `components/`, `lib/`, `styles/` and a public `index.js`
- `src/pages/` thin route wrappers, no logic
- `src/lib/` `apiClient.js` (`apiFetch`, `ApiError`), `queryClient.js`, `queryKeys.js`, `realtime/` (SSE)
- `src/config/env.js` the only place that reads `VITE_*`
- `src/components/ui/` shared UI (LoadingState, ErrorBanner, EmptyState, Modal)

## Conventions

- All server calls go through `apiFetch` in `src/lib/apiClient.js`. Errors arrive as `ApiError` with the backend's `code`.
- Server state is TanStack Query. Zustand (if added) holds UI chrome only.
- Import another feature only through its `index.js`.
- Live updates come from one SSE stream per project and patch the Query caches; never add polling.
- No keys or secrets here: `VITE_*` values end up in the browser bundle.
- Tests sit next to the code as `*.test.js(x)` (Vitest, jsdom, Testing Library). Setup: `src/test/setup.js`.
- Colours and text sizes come from the tokens in `src/index.css` (`var(--panel)`, `var(--text-sm)`, ...), never raw hex or px font sizes, so dark mode (`:root[data-theme="dark"]`) works everywhere. Exceptions: colours drawn on top of photos (box colours, canvas labels, thumbnail status dots) and white text on solid accent / ok / bad buttons.
- Light / Dark / Auto lives in `features/theme` (`useTheme`). `index.html` sets `data-theme` before the app loads with the same rule as `lib/theme.js`; keep them in step. Tests that need the computer's setting use `src/test/fakeMatchMedia.js`.

## Commands

```bash
npm ci
npm run dev        # http://localhost:5173, proxies /api to the backend on :8000
npm test
npm run lint
npm run build
```
