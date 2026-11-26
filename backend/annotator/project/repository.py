from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from annotator.project.models import Project


class ProjectRepository:
    def __init__(self, session: Session):
        self.session = session

    def list(self) -> list[Project]:
        return list(self.session.scalars(select(Project).order_by(Project.id.desc())))

    def get(self, project_id: int) -> Project | None:
        return self.session.get(Project, project_id)

    def create(self, name: str, description: str = "") -> Project:
        project = Project(name=name, description=description)
        self.session.add(project)
        self.session.flush()
        self.session.refresh(project)
        return project

    def save(self, project: Project) -> Project:
        """Write changes and move updated_at on (clock_timestamp: now() is fixed for the whole transaction)."""
        project.updated_at = func.clock_timestamp()
        self.session.flush()
        self.session.refresh(project)
        return project

    def delete(self, project_id: int) -> None:
        """The database removes everything under the project (classes, images, boxes, jobs, log: on delete cascade)."""
        self.session.execute(delete(Project).where(Project.id == project_id))
