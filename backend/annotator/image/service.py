import uuid
from dataclasses import dataclass
from pathlib import PurePath

from annotator.common.problem import ApiError
from annotator.common.text import one_line
from annotator.image.models import STATUSES
from annotator.image.repository import ImageRepository
from annotator.image.schemas import FILTERS, ImageList, ImageOut, SkippedFile, UploadResult
from annotator.image.thumbnails import IMAGE_EXTENSIONS, UnsupportedImageError, allowed_file_name, read_image
from annotator.project.service import ProjectService
from annotator.storage.storage_service import IMAGES_BUCKET, StorageError, StorageService

SIGNED_URL_SECONDS = 3600
NOT_AN_IMAGE_TYPE = f"not a supported image type ({', '.join(e.lstrip('.') for e in IMAGE_EXTENSIONS)})"


@dataclass(frozen=True)
class UploadedFile:
    file_name: str
    content: bytes
    content_type: str


def _base_name(name: str) -> str:
    """Drop any folder part a browser sends along ("shelf/day1/a.jpg" -> "a.jpg")."""
    return PurePath(name.replace("\\", "/")).name


class ImageService:
    def __init__(self, repo: ImageRepository, storage: StorageService, projects: ProjectService):
        self.repo = repo
        self.storage = storage
        self.projects = projects

    # ---------- upload ----------
    def upload(self, project_id: int, files: list[UploadedFile]) -> UploadResult:
        self.projects.get_project(project_id)
        names = [_base_name(f.file_name) for f in files]
        taken = {i.file_name for i in self.repo.find_by_names(project_id, names)}
        added, skipped = [], []
        for name, f in zip(names, files):
            if not allowed_file_name(name):
                skipped.append(SkippedFile(file_name=name, reason=NOT_AN_IMAGE_TYPE))
                continue
            if name in taken:
                skipped.append(SkippedFile(file_name=name, reason="already in this project"))
                continue
            try:
                info = read_image(f.content)
            except UnsupportedImageError:
                skipped.append(SkippedFile(file_name=name, reason="can't be opened as an image"))
                continue
            added.append(self._store(project_id, name, f, info))
            taken.add(name)
        return UploadResult(added=added, skipped=skipped)

    def _store(self, project_id: int, name: str, f: UploadedFile, info) -> ImageOut:
        key = uuid.uuid4().hex
        suffix = PurePath(name).suffix.lower()
        storage_path, thumb_path = f"{project_id}/{key}{suffix}", f"{project_id}/thumbs/{key}.jpg"
        try:
            self.storage.upload(IMAGES_BUCKET, storage_path, f.content, f.content_type or "application/octet-stream")
            self.storage.upload(IMAGES_BUCKET, thumb_path, info.thumbnail_jpeg, "image/jpeg")
        except StorageError as e:
            raise ApiError(502, "STORAGE_UNAVAILABLE", f"Couldn't save {name} to storage: {e}") from e
        row = self.repo.add(project_id, file_name=name, stem=PurePath(name).stem, storage_path=storage_path,
                            thumb_path=thumb_path, width=info.width, height=info.height)
        return ImageOut.model_validate(row)

    # ---------- read ----------
    def list_images(self, project_id: int, image_filter: str) -> ImageList:
        if image_filter not in FILTERS:
            raise ApiError(400, "UNKNOWN_FILTER", f"Unknown filter '{image_filter}'. Use one of: {', '.join(FILTERS)}.")
        self.projects.get_project(project_id)
        items = [ImageOut.model_validate(i) for i in self.repo.list_for_project(project_id, image_filter)]
        return ImageList(items=items, counts=self.repo.counts(project_id))

    def get_image(self, image_id: int) -> ImageOut:
        return ImageOut.model_validate(self._row(image_id))

    def ids_with_status(self, project_id: int, statuses: list[str] | None) -> list[int]:
        """Image ids by file name, for queueing AI work; None means every image."""
        self.projects.get_project(project_id)
        return self.repo.ids_with_status(project_id, statuses)

    def download_original(self, image_id: int) -> bytes:
        try:
            return self.storage.download(IMAGES_BUCKET, self._row(image_id).storage_path)
        except StorageError as e:
            raise ApiError(502, "STORAGE_UNAVAILABLE", f"Couldn't read image {image_id} from storage: {e}") from e

    # ---------- status and flag ----------
    def update_state(self, image_id: int, *, status: str | None = None, note: str | None = None,
                     flagged: bool | None = None, flag_reason: str | None = None,
                     flag_note: str | None = None) -> ImageOut:
        """Change only the fields given. The flag is separate from the status."""
        if status is not None and status not in STATUSES:
            raise ApiError(400, "UNKNOWN_STATUS", f"Unknown status '{status}'. Use one of: {', '.join(STATUSES)}.")
        row = self._row(image_id)
        for field, value in (("status", status), ("note", note), ("flagged", flagged),
                             ("flag_reason", flag_reason), ("flag_note", flag_note)):
            if value is not None:
                setattr(row, field, value)
        return ImageOut.model_validate(self.repo.save(row))

    def set_flag(self, image_id: int, flagged: bool, reason: str = "", note: str = "") -> ImageOut:
        """Flag "check this later" with a reason and note; unflagging clears both. The status is untouched."""
        if not flagged:
            reason = note = ""
        return self.update_state(image_id, flagged=flagged, flag_reason=one_line(reason), flag_note=one_line(note))

    def thumb_url(self, image_id: int) -> str:
        return self._signed(self._row(image_id).thumb_path)

    def file_url(self, image_id: int) -> str:
        return self._signed(self._row(image_id).storage_path)

    def _row(self, image_id: int):
        row = self.repo.get(image_id)
        if row is None:
            raise ApiError(404, "IMAGE_NOT_FOUND", f"Image {image_id} doesn't exist.")
        return row

    def _signed(self, path: str) -> str:
        try:
            return self.storage.signed_url(IMAGES_BUCKET, path, SIGNED_URL_SECONDS)
        except StorageError as e:
            raise ApiError(502, "STORAGE_UNAVAILABLE", f"Couldn't get a link from storage: {e}") from e
