# CLAUDE.md — backend (FastAPI + worker)

Root rules still apply: see [../CLAUDE.md](../CLAUDE.md).

## Layout

Package by feature under `annotator/`, same layers as backend_web with FastAPI file names:

| File | Layer | Rule |
|---|---|---|
| `router.py` | controller | Endpoints only. Calls its own feature's service. No logic, no queries |
| `service.py` | service | The rules. Raises `ApiError` for expected failures. Another feature is used only through its service |
| `repository.py` | repository | SQLAlchemy queries only |
| `models.py` | model | Table classes. Never returned from a router |
| `schemas.py` | DTO | Pydantic request/response shapes |

Shared code: `common/` (problem+json, paging), `config/settings.py` (the only place that reads env), `db/`, `storage/`, `realtime/`.

Two entry points, one codebase: the API (`annotator.main:create_app`) and the worker (`python -m annotator.worker`), which runs the AI engines.

## Hard rules

- Schema changes are a new Flyway file in `db/migration/` (`V<n>__snake_case.sql`), then add its `sha256sum` line to `db/migration/applied.sha256` once applied. Never edit an applied file.
- SQLAlchemy never creates tables (`create_all` is banned).
- Engine keys (`GEMINI_API_KEY` etc.) are read through `Settings`, never from `os.environ` directly.

## Tests

Mirror the package under `tests/` (e.g. `annotator/label/service.py` → `tests/label/test_service.py`).

```bash
.venv/Scripts/python -m pytest                  # unit + router tests
.venv/Scripts/python -m pytest -m db            # repository tests (Docker: testcontainers + Flyway)
.venv/Scripts/python -m pytest tests/legacy     # characterisation tests of today's app.py/backends.py
```

Setup: `python -m venv .venv` then `.venv/Scripts/python -m pip install -e ".[dev]"` (add `[detectors]` for Grounding DINO / YOLO-World).
