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

Live updates (`realtime/`): a V4 trigger sends `NOTIFY annotator_changes` with `{type, op, id, projectId}` on every committed change to `images`, `classes` or `activity_log` (V6: `jobs` sends one `{type, op, projectId}` per statement, answered with the job summary). `NotifyListener` (its own thread and connection) passes each payload to `RealtimeService.to_message`, which loads the DTO; the `Broadcaster` hands it to the SSE streams of that project (`GET /api/projects/{id}/events`). A new table joins by adding the same trigger and a branch in `to_message`.

Two entry points, one codebase: the API (`annotator.main:create_app`) and the worker (`python -m annotator.worker`), which runs the AI engines.

AI jobs: the API queues one `jobs` row per image (`job/service.py`). The worker (`job/loop.py`) claims the oldest with `FOR UPDATE SKIP LOCKED`; `labeling/service.py` then loads the image (short transaction), calls the engine (no transaction) and saves boxes, status and an `activity_log` line (short transaction). The worker wakes on the jobs NOTIFY and checks every 5 s anyway. Engines live in `engine/` (`registry.py` with each engine's options and their types, shared `vlm_prompts`, one folder per engine: `gemini/`, `claude_cli/`, `ollama/`, `detectors/`). VLMs get a copy of at most 1568 px (`labeling/image_prep.py`, with the 0–1000 grid when the engine's `grid` option is on); detectors get the original and can't refine. Detectors import torch only when they run, and keep one model loaded at a time (`detectors/common.py` `MODELS`). A usage limit (`LimitReached`) puts the job back in the queue and pauses that engine (`engine_pauses`) until `POST /api/worker/resume`. The worker's heartbeat (`worker_status/heartbeat.py`, every 15 s, engines re-checked every minute through `Probes`, the Gemini model list every 10 min) stores what each engine can do; `GET /api/engines` and the live `worker` message serve it.

Health check (`health/`): `GET /api/projects/{id}/health?low=100` builds today's report on request from the database: `service.py` loads classes, images and boxes through their services (`LabelService.boxes_by_image`), `report.py` (pure) counts. No table of its own. The web shows the images of a clicked class or issue as a picked-set filter.

Export (`export/`): today's YOLO zip and COCO JSON, built by the API on request and downloaded directly (no worker, nothing stored): `GET /api/projects/{id}/exports/{summary|yolo|coco}?onlyReviewed=&skipFlagged=`. `pick.py` chooses the images (labelled = `label.rules.is_labelled`, shared with the health check), `yolo.py` and `coco.py` (pure) build the files; the zip goes through a temp file that is deleted after sending.

## Hard rules

- Schema changes are a new Flyway file in `db/migration/` (`V<n>__snake_case.sql`), then add its `sha256sum` line to `db/migration/applied.sha256` once applied. Never edit an applied file.
- SQLAlchemy never creates tables (`create_all` is banned).
- Engine keys (`GEMINI_API_KEY` etc.) are read through `Settings`, never from `os.environ` directly.

## Run and test

Mirror the package under `tests/` (e.g. `annotator/label/service.py` → `tests/label/test_service.py`).

```bash
# Run the API (http://127.0.0.1:8000). Open browser tabs keep their live-update (SSE) stream connected,
# so --timeout-graceful-shutdown lets Ctrl+C finish instead of waiting for every tab to close.
.venv/Scripts/python -m uvicorn annotator.main:create_app --factory --host 127.0.0.1 --port 8000 --reload --timeout-graceful-shutdown 3

# Run the worker next to it (runs the AI engines; Gemini needs GEMINI_API_KEY set, see .env.example).
.venv/Scripts/python -m annotator.worker

.venv/Scripts/python -m pytest                  # unit + router tests
.venv/Scripts/python -m pytest -m db            # repository tests (Docker: testcontainers + Flyway)
```

Setup: `python -m venv .venv` then `.venv/Scripts/python -m pip install -e ".[dev]"` (add `[detectors]` for Grounding DINO / YOLO-World).
