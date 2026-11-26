from datetime import datetime

from annotator.common.schemas import ApiModel


class ProjectSummary(ApiModel):
    """One row on the projects page: the project plus how far its labelling is."""

    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    image_count: int
    unlabeled: int
    labelled: int       # auto + edited + reviewed
    reviewed: int       # approved
    to_approve: int     # auto + edited
    flagged: int
    errors: int
    class_count: int
    cover_image_id: int | None   # the first image added; None while the project has no images
    last_changed_at: datetime    # the later of the project's own edit and its newest image change
