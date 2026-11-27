from annotator.classes.service import ClassService
from annotator.common.problem import ApiError
from annotator.image.service import ImageService
from annotator.label.models import SOURCES
from annotator.label.repository import LabelRepository
from annotator.label.rules import clean_boxes
from annotator.label.schemas import BoxOut, ImageBoxes, SaveBoxes, SaveResult


class LabelService:
    """Boxes of an image: read, save from the editor (with a save-conflict check), replace (import / AI)."""

    def __init__(self, repo: LabelRepository, images: ImageService, classes: ClassService):
        self.repo = repo
        self.images = images
        self.classes = classes

    def replace_boxes(self, project_id: int, image_id: int, boxes: list[dict], source: str) -> int:
        """Swap the image's boxes for `boxes` after the save rules; returns how many were kept."""
        cleaned = clean_boxes(boxes)
        self.repo.replace(project_id, image_id, cleaned, source)
        return len(cleaned)

    def get_boxes(self, image_id: int) -> ImageBoxes:
        image = self.images.get_image(image_id)
        return ImageBoxes(boxes=self._boxes(image_id), updated_at=image.updated_at)

    def save(self, image_id: int, body: SaveBoxes) -> SaveResult:
        image = self.images.get_image(image_id)
        if image.updated_at != body.expected_updated_at:
            raise ApiError(409, "STALE_IMAGE", "This image was changed since you opened it (by someone else or the AI). "
                                               "Reload it to see the latest boxes.")
        known = {c.index for c in self.classes.list_classes(image.project_id)}
        for b in body.boxes:
            if b.cls not in known:
                raise ApiError(400, "UNKNOWN_CLASS", f"Class {b.cls} doesn't exist in this project.")
            if b.source not in SOURCES:
                raise ApiError(400, "BAD_BOX_SOURCE", f"Unknown box source '{b.source}'.")
        cleaned = clean_boxes([b.model_dump() for b in body.boxes])
        self.repo.replace(image.project_id, image_id, cleaned, source="human")
        updated = self.images.update_state(image_id, status=body.status)
        return SaveResult(image=updated, boxes=self._boxes(image_id))

    def has_outlines(self, image_id: int) -> bool:
        return any(b.points for b in self._boxes(image_id))

    def image_ids_with_outlines(self, project_id: int) -> set[int]:
        return self.repo.image_ids_with_outlines(project_id)

    def boxes_by_image(self, project_id: int) -> dict[int, list[dict]]:
        """All of the project's boxes as plain dicts (cls, x1..y2, source, conf, points), grouped by image id.
        Images without boxes are left out."""
        grouped: dict[int, list[dict]] = {}
        for row in self.repo.list_for_project(project_id):
            grouped.setdefault(row.image_id, []).append(BoxOut.model_validate(row).model_dump())
        return grouped

    def _boxes(self, image_id: int) -> list[BoxOut]:
        return [BoxOut.model_validate(b) for b in self.repo.list_for_image(image_id)]
