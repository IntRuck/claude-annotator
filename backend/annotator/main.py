"""FastAPI app factory. Feature routers are added here as each slice is built."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from annotator.activity.router import router as activity_router
from annotator.export.router import router as export_router
from annotator.health.router import router as health_router
from annotator.classes.router import router as classes_router
from annotator.common.problem import install_problem_handlers
from annotator.config.settings import Settings, get_settings
from annotator.image.router import router as image_router
from annotator.importer.router import router as import_router
from annotator.job.router import router as job_router
from annotator.label.router import router as label_router
from annotator.project.router import router as project_router
from annotator.realtime.broadcaster import RESYNC, Broadcaster
from annotator.realtime.dependencies import get_listener_factory, get_message_builder
from annotator.realtime.router import router as realtime_router
from annotator.storage.dependencies import get_storage
from annotator.storage.storage_service import IMAGES_BUCKET, StorageError
from annotator.worker_status.router import router as worker_status_router

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The bucket is created here, not in Flyway, so the migrations stay plain Postgres.
    storage = _resolve(app, get_storage)
    try:
        storage.ensure_bucket(IMAGES_BUCKET)
    except StorageError as e:
        log.warning("Couldn't check the storage buckets (is `supabase start` running?): %s", e)

    # Live updates: the NOTIFY listener thread feeds the broadcaster, which feeds every open SSE stream.
    broadcaster = Broadcaster()
    broadcaster.attach(asyncio.get_running_loop())
    app.state.broadcaster = broadcaster
    build_message = _resolve(app, get_message_builder)

    def forward(raw: str) -> None:
        result = build_message(raw)
        if result is None:
            return
        project_id, message = result
        if project_id is None:
            broadcaster.publish_all_from_thread(message)     # worker status: not about one project
        else:
            broadcaster.publish_from_thread(project_id, message)

    # On every (re)connect, open tabs refetch: changes made while the listener was away were missed.
    listener = _resolve(app, get_listener_factory)(
        on_payload=forward, on_connect=lambda: broadcaster.publish_all_from_thread(RESYNC))
    listener.start()
    try:
        yield
    finally:
        broadcaster.shutdown()
        listener.stop()


def _resolve(app: FastAPI, dependency):
    """Lifespan wiring that tests can swap through app.dependency_overrides, like request dependencies."""
    return app.dependency_overrides.get(dependency, dependency)()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="claude-annotator API", version="2.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_problem_handlers(app)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    app.include_router(project_router)
    app.include_router(classes_router)
    app.include_router(image_router)
    app.include_router(import_router)
    app.include_router(label_router)
    app.include_router(job_router)
    app.include_router(activity_router)
    app.include_router(health_router)
    app.include_router(export_router)
    app.include_router(worker_status_router)
    app.include_router(realtime_router)
    return app
