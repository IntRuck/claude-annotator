from annotator.common.schemas import ApiModel
from annotator.image.schemas import SkippedFile


class ImportResult(ApiModel):
    """What an import did, so the page can say it in plain words."""

    added: int
    skipped: list[SkippedFile]
    labelled: int
    boxes: int
    classes_created: list[str]
    placeholder_classes: list[str]
    kept_existing_classes: bool
    labels_without_image: list[str]
    bad_label_lines: int
    states_applied: int
    ignored_files: list[str]
    warnings: list[str]
