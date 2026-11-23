from sqlalchemy import select
from sqlalchemy.orm import Session

from annotator.project.models import Project


class ProjectRepository:
    def __init__(self, session: Session):
        self.session = session

    def list(self) -> list[Project]:
        return list(self.session.scalars(select(Project).order_by(Project.id.desc())))

    def get(self, project_id: int) -> Project | None:
        return self.session.get(Project, project_id)

    def create(self, name: str) -> Project:
        project = Project(name=name)
        self.session.add(project)
        self.session.flush()
        self.session.refresh(project)
        return project
