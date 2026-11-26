from datetime import datetime
from typing import Literal, get_args

from annotator.common.schemas import ApiModel

ImageFilter = Literal["all", "unlabeled", "auto", "edited", "reviewed", "flagged", "error"]
FILTERS = get_args(ImageFilter)


class ImageOut(ApiModel):
    id: int
    project_id: int
    file_name: str
    width: int
    height: int
    status: str
    note: str
    flagged: bool
    flag_reason: str
    flag_note: str
    box_count: int
    updated_at: datetime


class ImageList(ApiModel):
    items: list[ImageOut]
    counts: dict[str, int]


class SkippedFile(ApiModel):
    file_name: str
    reason: str


class UploadResult(ApiModel):
    added: list[ImageOut]
    skipped: list[SkippedFile]


class ProjectImageSummary(ApiModel):
    """One project's images in numbers, for the projects page."""

    all: int
    unlabeled: int
    auto: int
    edited: int
    reviewed: int
    flagged: int
    error: int
    last_changed_at: datetime
    cover_image_id: int


class FlagIn(ApiModel):
    flagged: bool
    reason: str = ""
    note: str = ""
