from datetime import datetime

from annotator.common.schemas import ApiModel

FILTERS = ("all", "unlabeled", "auto", "edited", "reviewed", "flagged", "error")


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


class FlagIn(ApiModel):
    flagged: bool
    reason: str = ""
    note: str = ""
