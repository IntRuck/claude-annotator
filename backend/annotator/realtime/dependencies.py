"""Wiring for live updates. Tests replace these through app.dependency_overrides."""
from collections.abc import Callable

from fastapi import Request

from annotator.activity.repository import ActivityRepository
from annotator.activity.service import ActivityService
from annotator.classes.repository import ClassRepository
from annotator.classes.service import ClassService
from annotator.db.session import libpq_dsn, open_session
from annotator.image.repository import ImageRepository
from annotator.image.service import ImageService
from annotator.job.repository import JobRepository
from annotator.job.service import JobService
from annotator.label.repository import LabelRepository
from annotator.label.service import LabelService
from annotator.project.repository import ProjectRepository
from annotator.project.service import ProjectService
from annotator.realtime.broadcaster import Broadcaster
from annotator.realtime.notify_listener import NotifyListener
from annotator.realtime.service import RealtimeService
from annotator.storage.dependencies import get_storage
from annotator.worker_status.repository import WorkerStatusRepository
from annotator.worker_status.service import WorkerStatusService

MessageBuilder = Callable[[str], tuple[int | None, dict] | None]   # project None = every open tab


def get_broadcaster(request: Request) -> Broadcaster:
    return request.app.state.broadcaster


def message_from_payload(raw: str) -> tuple[int, dict] | None:
    """Runs in the listener thread with its own short session (read only)."""
    with open_session() as session:
        projects = ProjectService(ProjectRepository(session))
        images = ImageService(ImageRepository(session), get_storage(), projects)
        classes = ClassService(ClassRepository(session), projects)
        activity = ActivityService(ActivityRepository(session), projects)
        labels = LabelService(LabelRepository(session), images, classes)
        jobs = JobService(JobRepository(session), projects, images, classes, activity, labels)
        engine_status = WorkerStatusService(WorkerStatusRepository(session))
        return RealtimeService(images, classes, jobs, activity, engine_status).to_message(raw)


def get_message_builder() -> MessageBuilder:
    return message_from_payload


def get_listener_factory() -> Callable[..., NotifyListener]:
    dsn = libpq_dsn()
    return lambda on_payload, on_connect: NotifyListener(dsn, on_payload=on_payload, on_connect=on_connect)
