"""FastAPI app factory. Feature routers are added here as each slice is built."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from annotator.classes.router import router as classes_router
from annotator.common.problem import install_problem_handlers
from annotator.config.settings import Settings, get_settings
from annotator.project.router import router as project_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="claude-annotator API", version="2.0.0")

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
    return app
