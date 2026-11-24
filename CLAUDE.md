# CLAUDE.md — claude-annotator

AI-assisted image labelling for object detection (YOLO). This is its own git repository.

**v2 is being built on `feat/supabase-v2`.** Today's app (`app.py`, `backends.py`, `index.html`) keeps working until v2 can do everything it does; then those files and `backend/tests/legacy/` are removed. Don't change today's app except to keep it running.

## Layout (v2)

| Folder | What | Rules |
|---|---|---|
| `backend/` | FastAPI API + worker (Python). See [backend/CLAUDE.md](backend/CLAUDE.md) | Package by feature; `router → service → repository → models`, `schemas` at the edges |
| `web/` | React 19 + Vite dashboard (plain JS). See [web/CLAUDE.md](web/CLAUDE.md) | Talks only to the backend API (REST + SSE), never to the database |
| `backend/db/migration/` | Flyway migrations (`V<n>__snake_case.sql`) | Never edit an applied migration; add a new version |
| `supabase/config.toml` | Local Supabase stack (Postgres + Storage), ports 55320–55327 | Stack only; Flyway owns the schema |
| `docker-compose.yml` | Flyway (pinned `flyway/flyway:11.3.4`), later api/worker/web | |

## Hard rules

- **Schema:** Flyway only. No `create_all`, no `supabase/migrations`. Applied files are listed in `backend/db/migration/applied.sha256` and guarded by `backend/tests/migrations`.
- **Live updates:** Postgres `NOTIFY` → backend listener → SSE `{ type, op, data }`. No polling loops in the web app.
- **Errors:** every API error is problem+json with a stable `code` and `traceId` (`annotator/common/problem.py`).
- **No login in v1:** the API listens on 127.0.0.1 and CORS allows only the web app. RLS stays on with no anon access; only the backend touches data.
- **Secrets:** never read or print any `.env`. Refer to variables by name. `.env.example` files are the templates. Engine keys live only in `backend/.env`, never in `web/`.
- **TDD:** a failing test first, then the smallest code to pass, then refactor. Moved code keeps its characterisation tests green.

## Commands

```bash
supabase start                                   # local stack (from the repo root)
docker compose run --rm flyway migrate          # apply migrations (also: info, validate)
cd backend && .venv/Scripts/python -m pytest      # backend tests (-m db needs Docker)
cd backend && .venv/Scripts/python -m uvicorn annotator.main:create_app --factory --port 8000 --reload --timeout-graceful-shutdown 3   # API
cd web && npm test && npm run lint && npm run build
```
