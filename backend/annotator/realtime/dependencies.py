"""Wiring for live updates. Tests replace these through app.dependency_overrides."""
from collections.abc import Callable

from fastapi import Request

from annotator.classes.repository import ClassRepository
from annotator.classes.service import ClassService
from annotator.db.session import libpq_dsn, open_session
from annotator.image.repository import ImageRepository
from annotator.image.service import ImageService
from annotator.project.repository import ProjectRepository
from annotator.project.service import ProjectService
from annotator.realtime.broadcaster import Broadcaster
from annotator.realtime.notify_listener import NotifyListener
from annotator.realtime.service import RealtimeService
from annotator.storage.dependencies import get_storage

MessageBuilder = Callable[[str], tuple[int, dict] | None]


def get_broadcaster(request: Request) -> Broadcaster:
    return request.app.state.broadcaster


def message_from_payload(raw: str) -> tuple[int, dict] | None:
    """Runs in the listener thread with its own short session (read only)."""
    with open_session() as session:
        projects = ProjectService(ProjectRepository(session))
        images = ImageService(ImageRepository(session), get_storage(), projects)
        return RealtimeService(images, ClassService(ClassRepository(session), projects)).to_message(raw)


def get_message_builder() -> MessageBuilder:
    return message_from_payload


def get_listener_factory() -> Callable[..., NotifyListener]:
    dsn = libpq_dsn()
    return lambda on_payload, on_connect: NotifyListener(dsn, on_payload=on_payload, on_connect=on_connect)
