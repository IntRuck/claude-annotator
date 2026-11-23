from annotator.common.problem import ApiError
from annotator.common.text import one_line
from annotator.project.repository import ProjectRepository
from annotator.project.schemas import ProjectOut


class ProjectService:
    def __init__(self, repo: ProjectRepository):
        self.repo = repo

    def list_projects(self) -> list[ProjectOut]:
        return [ProjectOut.model_validate(p) for p in self.repo.list()]

    def get_project(self, project_id: int) -> ProjectOut:
        project = self.repo.get(project_id)
        if project is None:
            raise ApiError(404, "PROJECT_NOT_FOUND", f"Project {project_id} doesn't exist.")
        return ProjectOut.model_validate(project)

    def create_project(self, name: str) -> ProjectOut:
        name = one_line(name)
        if not name:
            raise ApiError(400, "PROJECT_NAME_REQUIRED", "Give the project a name.")
        return ProjectOut.model_validate(self.repo.create(name))
