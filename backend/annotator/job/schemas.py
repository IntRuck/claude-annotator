from datetime import datetime
from typing import Literal

from annotator.common.schemas import ApiModel

JobKind = Literal["annotate", "refine"]
# Every target of either kind; which go with which kind is job/service.py TARGETS (refine: image / auto).
JobTarget = Literal["image", "unlabeled", "errors", "all", "auto"]


class JobCreate(ApiModel):
    """What to label and with which engine. `target`: image (needs imageId) / unlabeled (+ errors) / errors / all;
    refine takes image / auto."""

    kind: JobKind = "annotate"
    target: JobTarget
    image_id: int | None = None
    engine: str = "gemini"
    options: dict = {}


class QueueResult(ApiModel):
    matched: int          # images the target picked
    queued: int           # newly queued
    already_queued: int   # already waiting or being labelled


class StopResult(ApiModel):
    cancelled: int


class JobOut(ApiModel):
    id: int
    project_id: int
    image_id: int | None
    kind: str
    engine: str
    options: dict
    status: str
    error: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RunningJob(ApiModel):
    id: int
    image_id: int | None
    file_name: str
    engine: str
    kind: str
    started_at: datetime | None


class JobSummary(ApiModel):
    queued: int
    running: list[RunningJob]
