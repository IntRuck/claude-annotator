from annotator.activity.models import LEVELS
from annotator.activity.repository import ActivityRepository
from annotator.activity.schemas import ActivityOut
from annotator.common.problem import ApiError
from annotator.common.text import one_line
from annotator.project.service import ProjectService

MAX_MESSAGE = 1000
MAX_LIMIT = 500


class ActivityService:
    """The project's activity log: what the AI did, what was queued or stopped, and errors."""

    def __init__(self, repo: ActivityRepository, projects: ProjectService):
        self.repo = repo
        self.projects = projects

    def log(self, project_id: int, message: str, *, level: str = "info", job_id: int | None = None,
            image_id: int | None = None) -> ActivityOut:
        if level not in LEVELS:
            raise ValueError(f"unknown activity level {level!r}")
        text = one_line(message)[:MAX_MESSAGE]
        return ActivityOut.model_validate(self.repo.add(project_id, text, level=level, job_id=job_id, image_id=image_id))

    def list_recent(self, project_id: int, limit: int = 100) -> list[ActivityOut]:
        if not 1 <= limit <= MAX_LIMIT:
            raise ApiError(400, "BAD_LIMIT", f"limit must be between 1 and {MAX_LIMIT}.")
        self.projects.get_project(project_id)
        return [ActivityOut.model_validate(e) for e in self.repo.list_recent(project_id, limit)]

    def get_entry(self, entry_id: int) -> ActivityOut:
        entry = self.repo.get(entry_id)
        if entry is None:
            raise ApiError(404, "ACTIVITY_NOT_FOUND", f"Activity entry {entry_id} doesn't exist.")
        return ActivityOut.model_validate(entry)
