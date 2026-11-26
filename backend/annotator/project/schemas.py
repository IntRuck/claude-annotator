from datetime import datetime

from annotator.common.schemas import ApiModel


class ProjectCreate(ApiModel):
    name: str
    description: str = ""


class ProjectUpdate(ApiModel):
    """Only the fields sent change."""

    name: str | None = None
    description: str | None = None


class ProjectOut(ApiModel):
    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
