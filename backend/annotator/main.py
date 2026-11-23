"""FastAPI app factory. Feature routers are added here as each slice is built."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from annotator.classes.router import router as classes_router
from annotator.common.problem import install_problem_handlers
from annotator.config.settings import Settings, get_settings
from annotator.image.router import router as image_router
from annotator.importer.router import router as import_router
from annotator.project.router import router as project_router
from annotator.storage.dependencies import get_storage
from annotator.storage.storage_service import EXPORTS_BUCKET, IMAGES_BUCKET, StorageError

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Buckets are created here, not in Flyway, so the migrations stay plain Postgres.
    storage = app.dependency_overrides.get(get_storage, get_storage)()
    try:
        for bucket in (IMAGES_BUCKET, EXPORTS_BUCKET):
            storage.ensure_bucket(bucket)
    except StorageError as e:
        log.warning("Couldn't check the storage buckets (is `supabase start` running?): %s", e)
    yield


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
    return app
