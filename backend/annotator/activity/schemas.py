from datetime import datetime

from annotator.common.schemas import ApiModel


class ActivityOut(ApiModel):
    id: int
    level: str
    message: str
    job_id: int | None
    image_id: int | None
    created_at: datetime
