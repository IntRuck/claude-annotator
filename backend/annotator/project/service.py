from annotator.common.problem import ApiError
from annotator.common.text import one_line
from annotator.project.repository import ProjectRepository
from annotator.project.schemas import ProjectOut

MAX_DESCRIPTION = 200


def _name(text: str | None) -> str:
    name = one_line(text)
    if not name:
        raise ApiError(400, "PROJECT_NAME_REQUIRED", "Give the project a name.")
    return name


def _description(text: str | None) -> str:
    description = one_line(text)
    if len(description) > MAX_DESCRIPTION:
        raise ApiError(400, "PROJECT_DESCRIPTION_TOO_LONG",
                       f"Keep the description to {MAX_DESCRIPTION} characters (it has {len(description)}).")
    return description


class ProjectService:
    def __init__(self, repo: ProjectRepository):
        self.repo = repo

    def list_projects(self) -> list[ProjectOut]:
        return [ProjectOut.model_validate(p) for p in self.repo.list()]

    def get_project(self, project_id: int) -> ProjectOut:
        return ProjectOut.model_validate(self._row(project_id))

    def create_project(self, name: str, description: str = "") -> ProjectOut:
        return ProjectOut.model_validate(self.repo.create(_name(name), _description(description)))

    def update_project(self, project_id: int, *, name: str | None = None,
                       description: str | None = None) -> ProjectOut:
        """Change only the fields given (None = keep)."""
        row = self._row(project_id)
        if name is not None:
            row.name = _name(name)
        if description is not None:
            row.description = _description(description)
        return ProjectOut.model_validate(self.repo.save(row))

    def delete_project(self, project_id: int) -> None:
        """Database rows only. The photo files are removed by overview's delete, which calls this."""
        self._row(project_id)
        self.repo.delete(project_id)

    def _row(self, project_id: int):
        project = self.repo.get(project_id)
        if project is None:
            raise ApiError(404, "PROJECT_NOT_FOUND", f"Project {project_id} doesn't exist.")
        return project
