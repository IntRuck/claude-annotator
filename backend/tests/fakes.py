"""In-memory repositories for service and router tests (no database).

Each fake follows the same contract as the real repository it replaces; the real ones are covered by the
`db` tests against Postgres.
"""
from datetime import datetime, timezone

from annotator.classes.models import ProjectClass
from annotator.classes.repository import ClassNameTakenError
from annotator.image.models import Image
from annotator.project.models import Project

NOW = datetime(2026, 11, 23, tzinfo=timezone.utc)


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


class FakeImageRepository:
    def __init__(self):
        self.rows: dict[int, Image] = {}

    def get(self, image_id: int) -> Image | None:
        return self.rows.get(image_id)

    def _of(self, project_id: int) -> list[Image]:
        return sorted((r for r in self.rows.values() if r.project_id == project_id), key=lambda r: r.file_name)

    def list_for_project(self, project_id: int, image_filter: str) -> list[Image]:
        rows = self._of(project_id)
        if image_filter == "flagged":
            return [r for r in rows if r.flagged]
        return rows if image_filter == "all" else [r for r in rows if r.status == image_filter]

    def counts(self, project_id: int) -> dict[str, int]:
        rows = self._of(project_id)
        counts = {"all": len(rows)}
        for key in ("unlabeled", "auto", "edited", "reviewed", "flagged", "error"):
            counts[key] = len(self.list_for_project(project_id, key))
        return counts

    def find_by_names(self, project_id: int, names: list[str]) -> list[Image]:
        return [r for r in self._of(project_id) if r.file_name in names]

    def add(self, project_id: int, *, file_name, stem, storage_path, thumb_path, width, height) -> Image:
        row = Image(id=len(self.rows) + 1, project_id=project_id, file_name=file_name, stem=stem,
                    storage_path=storage_path, thumb_path=thumb_path, width=width, height=height,
                    status="unlabeled", note="", flagged=False, flag_reason="", flag_note="", box_count=0,
                    created_at=NOW, updated_at=NOW)
        self.rows[row.id] = row
        return row


class FakeStorage:
    """Stores objects in a dict. Set `fail_with` to make every call raise that error."""

    def __init__(self):
        self.objects: dict[tuple[str, str], tuple[bytes, str]] = {}
        self.buckets: list[str] = []
        self.fail_with: Exception | None = None

    def _check(self):
        if self.fail_with:
            raise self.fail_with

    def ensure_bucket(self, bucket: str) -> None:
        self._check()
        if bucket not in self.buckets:
            self.buckets.append(bucket)

    def upload(self, bucket: str, path: str, data: bytes, content_type: str) -> None:
        self._check()
        self.objects[(bucket, path)] = (data, content_type)

    def download(self, bucket: str, path: str) -> bytes:
        self._check()
        return self.objects[(bucket, path)][0]

    def signed_url(self, bucket: str, path: str, expires_in: int) -> str:
        self._check()
        return f"http://storage.test/{bucket}/{path}?expires={expires_in}"

    def remove(self, bucket: str, paths: list[str]) -> None:
        self._check()
        for p in paths:
            self.objects.pop((bucket, p), None)
