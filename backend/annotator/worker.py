"""The worker process: `python -m annotator.worker` (run it next to the API).

It runs the AI engines, so slow calls and GPU memory stay out of the API. It wakes on a NOTIFY from the jobs
table (the same channel the API's live updates use) and checks the queue every few seconds anyway.
"""
import json
import logging
import os
import socket
import threading
from collections.abc import Callable
from contextlib import contextmanager
from functools import partial
from types import SimpleNamespace

from sqlalchemy.orm import Session

from annotator.activity.repository import ActivityRepository
from annotator.activity.service import ActivityService
from annotator.classes.repository import ClassRepository
from annotator.classes.service import ClassService
from annotator.config.settings import Settings, get_settings
from annotator.db.session import libpq_dsn, open_session
from annotator.engine.gemini.client import GeminiEngine
from annotator.engine.registry import make_engine
from annotator.image.repository import ImageRepository
from annotator.image.service import ImageService
from annotator.job.loop import JobLoop
from annotator.job.repository import JobRepository
from annotator.job.service import JobService
from annotator.label.repository import LabelRepository
from annotator.label.service import LabelService
from annotator.labeling.service import LabelingService
from annotator.project.repository import ProjectRepository
from annotator.project.service import ProjectService
from annotator.realtime.notify_listener import NotifyListener
from annotator.storage.dependencies import get_storage
from annotator.storage.storage_service import StorageService
from annotator.worker_status.heartbeat import Heartbeat, engine_availability
from annotator.worker_status.repository import WorkerStatusRepository
from annotator.worker_status.service import WorkerStatusService

log = logging.getLogger("annotator.worker")


def wakes_worker(raw: str) -> bool:
    """New or changed jobs, and worker/pause changes (a Resume) are worth a look at the queue."""
    try:
        return json.loads(raw).get("type") in ("jobs", "worker")
    except (ValueError, AttributeError):
        return False


def build_services(session: Session, storage: StorageService) -> SimpleNamespace:
    projects = ProjectService(ProjectRepository(session))
    images = ImageService(ImageRepository(session), storage, projects)
    classes = ClassService(ClassRepository(session), projects)
    activity = ActivityService(ActivityRepository(session), projects)
    jobs = JobService(JobRepository(session), projects, images, classes, activity)
    labels = LabelService(LabelRepository(session), images, classes)
    engine_status = WorkerStatusService(WorkerStatusRepository(session))
    return SimpleNamespace(jobs=jobs, engine_status=engine_status,
                           labeling=LabelingService(jobs, images, classes, labels, activity, engine_status))


def make_unit(session_factory: Callable[[], Session], storage: StorageService):
    """One unit of work = one session: commit when the step succeeds, roll back when it fails."""
    @contextmanager
    def unit():
        session = session_factory()
        try:
            yield build_services(session, storage)
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    return unit


def make_heartbeat(unit, worker_id: str, settings: Settings) -> Heartbeat:
    def beat(engines: dict) -> None:
        with unit() as s:
            s.engine_status.heartbeat(worker_id, engines)

    def gone() -> None:
        with unit() as s:
            s.engine_status.stopped(worker_id)

    gemini = GeminiEngine(api_key=settings.gemini_api_key, base_url=settings.gemini_base_url)
    return Heartbeat(beat, gone, availability=partial(engine_availability, settings, gemini.list_models))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    wake, stop = threading.Event(), threading.Event()
    unit = make_unit(open_session, get_storage())
    listener = NotifyListener(libpq_dsn(), on_payload=lambda raw: wake.set() if wakes_worker(raw) else None,
                              on_connect=wake.set)
    heartbeat = make_heartbeat(unit, f"{socket.gethostname()}:{os.getpid()}", settings)
    loop = JobLoop(unit, partial(make_engine, settings=settings), wake=wake, stop=stop)
    listener.start()
    heartbeat.start()
    log.info("Worker started; waiting for jobs (Ctrl+C stops it; an image cut off goes back in the queue)")
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        log.info("Stopping")
    finally:
        stop.set()
        heartbeat.stop()
        listener.stop()


if __name__ == "__main__":
    main()
