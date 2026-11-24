"""Live-update rules: which database changes become which browser messages, and who may open a stream."""
import json
import logging

from annotator.activity.service import ActivityService
from annotator.classes.service import ClassService
from annotator.common.problem import ApiError
from annotator.image.service import ImageService
from annotator.job.service import JobService
from annotator.project.service import ProjectService
from annotator.realtime.broadcaster import Broadcaster, Subscription
from annotator.worker_status.service import WorkerStatusService

log = logging.getLogger(__name__)

OPS = ("insert", "update", "delete")


class RealtimeService:
    """Turns a NOTIFY payload from a trigger into the message the browser gets: `{type, op, data}`.

    - images / classes / activity (`{type, op, id, projectId}`): `data` is the same DTO the REST API returns,
      or just the id for a delete.
    - jobs (`{type, op, projectId}`, one per statement): `{type: "jobs", op: "summary", data: JobSummary}`.
    - worker (heartbeats and engine pauses, no project): `{type: "worker", op: "status", data: EngineStatus}`,
      returned with project None, which means every open tab.
    """

    def __init__(self, images: ImageService, classes: ClassService, jobs: JobService, activity: ActivityService,
                 engine_status: WorkerStatusService):
        self.images = images
        self.classes = classes
        self.jobs = jobs
        self.activity = activity
        self.engine_status = engine_status

    def to_message(self, raw: str) -> tuple[int | None, dict] | None:
        try:
            payload = json.loads(raw)
            kind, op, project_id = payload["type"], payload["op"], payload["projectId"]
            if op not in OPS:
                return None
            if kind == "jobs":
                return project_id, self._jobs(project_id)
            if kind == "worker":
                return None, {"type": "worker", "op": "status",
                              "data": self.engine_status.status().model_dump(by_alias=True, mode="json")}
            row_id = payload["id"]
        except (ValueError, KeyError, TypeError):
            log.warning("Live updates: skipped a payload it couldn't read: %.200s", raw)
            return None
        if kind == "images":
            return project_id, self._image(op, row_id)
        if kind == "classes":
            return project_id, self._class(op, project_id, row_id)
        if kind == "activity":
            message = self._activity(op, row_id)
            return (project_id, message) if message else None
        return None

    def _jobs(self, project_id: int) -> dict:
        return {"type": "jobs", "op": "summary", "data": self.jobs.summary(project_id).model_dump(by_alias=True, mode="json")}

    def _activity(self, op: str, entry_id: int) -> dict | None:
        if op != "insert":
            return None
        try:
            entry = self.activity.get_entry(entry_id)
        except ApiError:
            return None
        return {"type": "activity", "op": "insert", "data": entry.model_dump(by_alias=True, mode="json")}

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
