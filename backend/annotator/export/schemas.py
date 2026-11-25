from annotator.common.schemas import ApiModel


class ExportSummary(ApiModel):
    """What an export with these options would contain (shown in the dialog before downloading)."""

    images: int
    boxes: int
    train: int  # YOLO split
    val: int
