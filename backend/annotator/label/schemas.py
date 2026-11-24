from datetime import datetime

from pydantic import AliasChoices, Field

from annotator.common.schemas import ApiModel
from annotator.image.schemas import ImageOut


class BoxIn(ApiModel):
    """A box from the editor: class index and corners as fractions of the image (0-1)."""

    cls: int = Field(ge=0)
    x1: float
    y1: float
    x2: float
    y2: float
    source: str = "human"  # boxes the editor didn't change keep where they came from (ai / import)
    conf: float | None = None


class BoxOut(ApiModel):
    cls: int = Field(validation_alias=AliasChoices("class_index", "cls"))
    x1: float
    y1: float
    x2: float
    y2: float
    source: str
    conf: float | None = None


class ImageBoxes(ApiModel):
    boxes: list[BoxOut]
    updated_at: datetime  # send it back when saving, so a newer save by someone else isn't overwritten


class SaveBoxes(ApiModel):
    boxes: list[BoxIn]
    status: str  # "edited" (S) or "reviewed" (Approve / R)
    expected_updated_at: datetime


class SaveResult(ApiModel):
    image: ImageOut
    boxes: list[BoxOut]
