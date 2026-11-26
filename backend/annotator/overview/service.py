"""The projects page: every project with its numbers, and deleting a whole project (rows and photo files).

It sits above the project, image and classes features, like health/ does: ImageService already depends on
ProjectService, so the project feature can't reach the image files itself.
"""
import logging

from annotator.classes.service import ClassService
from annotator.common.problem import ApiError
from annotator.image.service import ImageService
from annotator.overview.schemas import ProjectSummary
from annotator.project.service import ProjectService

log = logging.getLogger(__name__)


class OverviewService:
    def __init__(self, projects: ProjectService, images: ImageService, classes: ClassService):
        self.projects = projects
        self.images = images
        self.classes = classes

    def summaries(self) -> list[ProjectSummary]:
        """Most recently changed first."""
        numbers = self.images.summary_by_project()
        class_counts = self.classes.count_by_project()
        rows = []
        for p in self.projects.list_projects():
            n = numbers.get(p.id)
            rows.append(ProjectSummary(
                id=p.id, name=p.name, description=p.description, created_at=p.created_at, updated_at=p.updated_at,
                image_count=n.all if n else 0,
                unlabeled=n.unlabeled if n else 0,
                labelled=n.auto + n.edited + n.reviewed if n else 0,
                reviewed=n.reviewed if n else 0,
                to_approve=n.auto + n.edited if n else 0,
                flagged=n.flagged if n else 0,
                errors=n.error if n else 0,
                class_count=class_counts.get(p.id, 0),
                cover_image_id=n.cover_image_id if n else None,
                last_changed_at=max(p.updated_at, n.last_changed_at) if n else p.updated_at,
            ))
        return sorted(rows, key=lambda r: r.last_changed_at, reverse=True)

    def delete_project(self, project_id: int) -> None:
        """Rows first (the database cascades to everything under the project), then the photo files. Files left
        behind when storage is down do no harm, so that only logs a warning."""
        self.projects.get_project(project_id)
        paths = self.images.file_paths(project_id)
        self.projects.delete_project(project_id)
        try:
            self.images.delete_files(paths)
        except ApiError as e:
            log.warning("Project %s deleted, but %d photo files stay in storage: %s", project_id, len(paths), e.detail)
