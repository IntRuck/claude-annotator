from annotator.classes.repository import ClassNameTakenError, ClassRepository
from annotator.classes.schemas import ClassCreate, ClassOut, ClassUpdate
from annotator.common.problem import ApiError
from annotator.common.text import clean_class_name, one_line
from annotator.project.service import ProjectService


def _name_taken(name: str) -> ApiError:
    return ApiError(409, "CLASS_NAME_TAKEN", f'A class called "{name}" already exists in this project.')


def _clean_required_name(raw: str) -> str:
    name = clean_class_name(raw)
    if not name:
        raise ApiError(400, "CLASS_NAME_REQUIRED", "Give the class a name.")
    return name


class ClassService:
    """SKU list of a project. New classes go at the end and an index never changes, so YOLO labels stay valid."""

    def __init__(self, repo: ClassRepository, projects: ProjectService):
        self.repo = repo
        self.projects = projects

    def list_classes(self, project_id: int) -> list[ClassOut]:
        self.projects.get_project(project_id)
        return [ClassOut.model_validate(c) for c in self.repo.list_for_project(project_id)]

    def get_class(self, project_id: int, class_index: int) -> ClassOut:
        row = self.repo.get(project_id, class_index)
        if row is None:
            raise ApiError(404, "CLASS_NOT_FOUND", f"Class {class_index} doesn't exist in this project.")
        return ClassOut.model_validate(row)

    def add_class(self, project_id: int, body: ClassCreate) -> ClassOut:
        self.projects.get_project(project_id)
        name = _clean_required_name(body.name)
        if self.repo.find_by_name(project_id, name):
            raise _name_taken(name)
        try:
            row = self.repo.add(project_id, name, one_line(body.detector_prompt), one_line(body.description))
        except ClassNameTakenError:
            raise _name_taken(name) from None
        return ClassOut.model_validate(row)

    def update_class(self, project_id: int, class_index: int, body: ClassUpdate) -> ClassOut:
        row = self.repo.get(project_id, class_index)
        if row is None:
            self.projects.get_project(project_id)
            raise ApiError(404, "CLASS_NOT_FOUND", f"Class {class_index} doesn't exist in this project.")
        if body.name is not None:
            name = _clean_required_name(body.name)
            clash = self.repo.find_by_name(project_id, name)
            if clash is not None and clash.class_index != class_index:
                raise _name_taken(name)
            row.name = name
        if body.detector_prompt is not None:
            row.detector_prompt = one_line(body.detector_prompt)
        if body.description is not None:
            row.description = one_line(body.description)
        try:
            row = self.repo.save(row)
        except ClassNameTakenError:
            raise _name_taken(row.name) from None
        return ClassOut.model_validate(row)

    # ---------- import ----------
    def import_classes(self, project_id: int, entries: list[tuple[str, str, str]]) -> list[str]:
        """Add a whole class list (name, detector prompt, description) to a project that has no classes yet.
        Every line gets the next index, even a repeated or blank name, so imported label IDs stay right.
        Returns the names created (empty when the project already had classes)."""
        self.projects.get_project(project_id)
        if self.repo.list_for_project(project_id):
            return []
        created = []
        for index, (raw_name, prompt, description) in enumerate(entries):
            name = self._free_name(project_id, clean_class_name(raw_name) or f"class_{index}", index)
            self.repo.add(project_id, name, one_line(prompt), one_line(description))
            created.append(name)
        return created

    def ensure_indexes(self, project_id: int, max_index: int) -> list[str]:
        """Make sure class IDs 0..max_index exist, adding placeholders (class_<n>) that can be renamed later."""
        existing = self.repo.list_for_project(project_id)
        start = existing[-1].class_index + 1 if existing else 0
        created = []
        for index in range(start, max_index + 1):
            name = self._free_name(project_id, f"class_{index}", index)
            self.repo.add(project_id, name, "", "")
            created.append(name)
        return created

    def _free_name(self, project_id: int, base: str, index: int) -> str:
        candidate, n = base, 1
        while self.repo.find_by_name(project_id, candidate):
            candidate = f"{base}_{index}" if n == 1 else f"{base}_{index}_{n}"
            n += 1
        return candidate
