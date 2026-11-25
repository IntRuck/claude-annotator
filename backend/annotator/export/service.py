from typing import BinaryIO

from annotator.classes.service import ClassService
from annotator.export import coco, yolo
from annotator.export.pick import Picked, pick
from annotator.export.schemas import ExportSummary
from annotator.image.service import ImageService
from annotator.label.service import LabelService


class ExportService:
    """Today's YOLO zip and COCO JSON, built on request from the database and storage and downloaded directly.
    Options as today: `only_reviewed` (approved images only, off by default) and `skip_flagged` (on by default)."""

    def __init__(self, images: ImageService, classes: ClassService, labels: LabelService):
        self.images = images
        self.classes = classes
        self.labels = labels

    def summary(self, project_id: int, only_reviewed: bool = False, skip_flagged: bool = True) -> ExportSummary:
        _, picked = self._load(project_id, only_reviewed, skip_flagged)
        parts = list(yolo.split(picked).values())
        return ExportSummary(images=len(picked), boxes=sum(len(p.boxes) for p in picked),
                             train=parts.count("train"), val=parts.count("val"))

    def write_yolo(self, project_id: int, out: BinaryIO, only_reviewed: bool = False,
                   skip_flagged: bool = True) -> None:
        classes, picked = self._load(project_id, only_reviewed, skip_flagged)
        yolo.write_zip(out, classes, picked, lambda image: self.images.download_original(image.id))

    def coco(self, project_id: int, only_reviewed: bool = False, skip_flagged: bool = True) -> dict:
        return coco.build(*self._load(project_id, only_reviewed, skip_flagged))

    def _load(self, project_id: int, only_reviewed: bool, skip_flagged: bool) -> tuple[list[tuple[int, str]],
                                                                                       list[Picked]]:
        classes = [(c.index, c.name) for c in self.classes.list_classes(project_id)]  # also checks the project
        images = self.images.list_images(project_id, "all").items
        picked = pick(images, self.labels.boxes_by_image(project_id), only_reviewed=only_reviewed,
                      skip_flagged=skip_flagged)
        return classes, picked
