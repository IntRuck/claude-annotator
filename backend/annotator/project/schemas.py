from datetime import datetime

from annotator.common.schemas import ApiModel


class ProjectCreate(ApiModel):
    name: str


class ProjectOut(ApiModel):
    id: int
    name: str
    created_at: datetime
