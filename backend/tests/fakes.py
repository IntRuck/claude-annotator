"""In-memory repositories for service and router tests (no database).

Each fake follows the same contract as the real repository it replaces; the real ones are covered by the
`db` tests against Postgres.
"""
from datetime import datetime, timezone

from annotator.classes.models import ProjectClass
from annotator.classes.repository import ClassNameTakenError
from annotator.project.models import Project


class FakeProjectRepository:
    def __init__(self):
        self.rows: dict[int, Project] = {}

    def list(self) -> list[Project]:
        return sorted(self.rows.values(), key=lambda p: p.id, reverse=True)

    def get(self, project_id: int) -> Project | None:
        return self.rows.get(project_id)

    def create(self, name: str) -> Project:
        project = Project(id=len(self.rows) + 1, name=name, created_at=datetime(2026, 11, 23, tzinfo=timezone.utc))
        self.rows[project.id] = project
        return project


class FakeClassRepository:
    def __init__(self):
        self.rows: dict[tuple[int, int], ProjectClass] = {}

    def list_for_project(self, project_id: int) -> list[ProjectClass]:
        return sorted((c for (p, _), c in self.rows.items() if p == project_id), key=lambda c: c.class_index)

    def get(self, project_id: int, class_index: int) -> ProjectClass | None:
        return self.rows.get((project_id, class_index))

    def find_by_name(self, project_id: int, name: str) -> ProjectClass | None:
        return next((c for c in self.list_for_project(project_id) if c.name.lower() == name.lower()), None)

    def add(self, project_id: int, name: str, detector_prompt: str, description: str) -> ProjectClass:
        if self.find_by_name(project_id, name):
            raise ClassNameTakenError(name)
        index = len(self.list_for_project(project_id))
        row = ProjectClass(project_id=project_id, class_index=index, name=name,
                           detector_prompt=detector_prompt, description=description)
        self.rows[(project_id, index)] = row
        return row

    def save(self, row: ProjectClass) -> ProjectClass:
        clash = self.find_by_name(row.project_id, row.name)
        if clash is not None and clash.class_index != row.class_index:
            raise ClassNameTakenError(row.name)
        self.rows[(row.project_id, row.class_index)] = row
        return row
