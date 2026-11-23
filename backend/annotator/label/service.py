from annotator.label.repository import LabelRepository
from annotator.label.rules import clean_boxes


class LabelService:
    """Boxes of an image. Saving from the editor (status, conflicts) comes with the editor slice."""

    def __init__(self, repo: LabelRepository):
        self.repo = repo

    def replace_boxes(self, project_id: int, image_id: int, boxes: list[dict], source: str) -> int:
        """Swap the image's boxes for `boxes` after the save rules; returns how many were kept."""
        cleaned = clean_boxes(boxes)
        self.repo.replace(project_id, image_id, cleaned, source)
        return len(cleaned)
