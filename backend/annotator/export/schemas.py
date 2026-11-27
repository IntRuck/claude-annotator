from typing import Literal

from annotator.common.schemas import ApiModel

# boxes = today's files; outlines = YOLO segmentation / COCO segmentation, fully outlined images only.
Shape = Literal["boxes", "outlines"]


class ExportSummary(ApiModel):
    """What an export with these options would contain (shown in the dialog before downloading)."""

    images: int
    boxes: int
    train: int  # YOLO split
    val: int
    left_out: int = 0  # outlines: images left out because some objects have no outline
