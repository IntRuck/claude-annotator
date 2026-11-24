"""Live-update rules: which database changes become which browser messages, and who may open a stream."""
import json
import logging

from annotator.classes.service import ClassService
from annotator.common.problem import ApiError
from annotator.image.service import ImageService
from annotator.project.service import ProjectService
from annotator.realtime.broadcaster import Broadcaster, Subscription

log = logging.getLogger(__name__)

OPS = ("insert", "update", "delete")


class RealtimeService:
    """Turns a NOTIFY payload from a V4 trigger (`{type, op, id, projectId}`) into the message the browser gets:
    `{type, op, data}` where `data` is the same DTO the REST API returns (or just the id for a delete)."""

    def __init__(self, images: ImageService, classes: ClassService):
        self.images = images
        self.classes = classes

    def to_message(self, raw: str) -> tuple[int, dict] | None:
        try:
            payload = json.loads(raw)
            kind, op, row_id, project_id = payload["type"], payload["op"], payload["id"], payload["projectId"]
        except (ValueError, KeyError, TypeError):
            log.warning("Live updates: skipped a payload it couldn't read: %.200s", raw)
            return None
        if op not in OPS:
            return None
        if kind == "images":
            return project_id, self._image(op, row_id)
        if kind == "classes":
            return project_id, self._class(op, project_id, row_id)
        return None

    def _image(self, op: str, image_id: int) -> dict:
        gone = {"type": "images", "op": "delete", "data": {"id": image_id}}
        if op == "delete":
            return gone
        try:
            image = self.images.get_image(image_id)
        except ApiError:
            return gone  # deleted again before we got to read it
        return {"type": "images", "op": op, "data": image.model_dump(by_alias=True, mode="json")}

    def _class(self, op: str, project_id: int, class_index: int) -> dict:
        gone = {"type": "classes", "op": "delete", "data": {"index": class_index}}
        if op == "delete":
            return gone
        try:
            cls = self.classes.get_class(project_id, class_index)
        except ApiError:
            return gone
        return {"type": "classes", "op": op, "data": cls.model_dump(by_alias=True, mode="json")}


class EventStreamService:
    """Opens the live stream of one project for one browser tab."""

    def __init__(self, projects: ProjectService, broadcaster: Broadcaster):
        self.projects = projects
        self.broadcaster = broadcaster

    def open(self, project_id: int) -> Subscription:
        self.projects.get_project(project_id)
        return self.broadcaster.subscribe(project_id)
