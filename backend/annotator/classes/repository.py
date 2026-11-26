from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from annotator.classes.models import ProjectClass
from annotator.project.models import Project


class ClassNameTakenError(Exception):
    """Another class in the project already has this name (ignoring capitals)."""


class ClassRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_for_project(self, project_id: int) -> list[ProjectClass]:
        stmt = select(ProjectClass).where(ProjectClass.project_id == project_id).order_by(ProjectClass.class_index)
        return list(self.session.scalars(stmt))

    def count_by_project(self) -> dict[int, int]:
        """Number of classes per project; projects without classes are left out."""
        rows = self.session.execute(
            select(ProjectClass.project_id, func.count()).group_by(ProjectClass.project_id))
        return {project_id: count for project_id, count in rows}

    def get(self, project_id: int, class_index: int) -> ProjectClass | None:
        return self.session.get(ProjectClass, (project_id, class_index))

    def find_by_name(self, project_id: int, name: str) -> ProjectClass | None:
        stmt = select(ProjectClass).where(
            ProjectClass.project_id == project_id, func.lower(ProjectClass.name) == name.lower())
        return self.session.scalars(stmt).first()

    def add(self, project_id: int, name: str, detector_prompt: str, description: str) -> ProjectClass:
        # Lock the project row so two adds at once can't pick the same next index.
        self.session.execute(select(Project.id).where(Project.id == project_id).with_for_update())
        next_index = self.session.scalar(
            select(func.coalesce(func.max(ProjectClass.class_index) + 1, 0)).where(ProjectClass.project_id == project_id))
        row = ProjectClass(project_id=project_id, class_index=next_index, name=name,
                           detector_prompt=detector_prompt, description=description)
        return self._flush(row)

    def save(self, row: ProjectClass) -> ProjectClass:
        return self._flush(row)

    def _flush(self, row: ProjectClass) -> ProjectClass:
        # add + flush inside a savepoint: if the name is taken, only this change is undone (a pending row is
        # dropped from the session) and the rest of the request's transaction stays usable.
        try:
            with self.session.begin_nested():
                self.session.add(row)
                self.session.flush()
        except IntegrityError as e:
            if "classes_project_name_ci" in str(e.orig):
                raise ClassNameTakenError(row.name) from e
            raise
        return row
