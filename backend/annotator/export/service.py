from typing import BinaryIO

from annotator.classes.service import ClassService
from annotator.export import coco, yolo
from annotator.export.pick import Picked, fully_outlined, pick
from annotator.export.schemas import ExportSummary, Shape
from annotator.image.service import ImageService
from annotator.label.service import LabelService


class ExportService:
    """Today's YOLO zip and COCO JSON, built on request from the database and storage and downloaded directly.
    Options as today: `only_reviewed` (approved images only, off by default) and `skip_flagged` (on by default).
    `shape` "outlines" exports outlines instead of boxes, from fully outlined images only."""

    def __init__(self, images: ImageService, classes: ClassService, labels: LabelService):
        self.images = images
        self.classes = classes
        self.labels = labels

    def summary(self, project_id: int, only_reviewed: bool = False, skip_flagged: bool = True,
                shape: Shape = "boxes") -> ExportSummary:
        _, picked, left_out = self._load(project_id, only_reviewed, skip_flagged, shape)
        parts = list(yolo.split(picked).values())
        return ExportSummary(images=len(picked), boxes=sum(len(p.boxes) for p in picked),
                             train=parts.count("train"), val=parts.count("val"), left_out=left_out)

    def write_yolo(self, project_id: int, out: BinaryIO, only_reviewed: bool = False,
                   skip_flagged: bool = True, shape: Shape = "boxes") -> None:
        classes, picked, _ = self._load(project_id, only_reviewed, skip_flagged, shape)
        yolo.write_zip(out, classes, picked, lambda image: self.images.download_original(image.id), shape=shape)

    def coco(self, project_id: int, only_reviewed: bool = False, skip_flagged: bool = True,
             shape: Shape = "boxes") -> dict:
        classes, picked, _ = self._load(project_id, only_reviewed, skip_flagged, shape)
        return coco.build(classes, picked, shape)

    def _load(self, project_id: int, only_reviewed: bool, skip_flagged: bool,
              shape: Shape) -> tuple[list[tuple[int, str]], list[Picked], int]:
        classes = [(c.index, c.name) for c in self.classes.list_classes(project_id)]  # also checks the project
        images = self.images.list_images(project_id, "all").items
        picked = pick(images, self.labels.boxes_by_image(project_id), only_reviewed=only_reviewed,
                      skip_flagged=skip_flagged)
        if shape == "outlines":
            return classes, *fully_outlined(picked)
        return classes, picked, 0
