from sqlalchemy import select
from sqlalchemy.orm import Session

from annotator.activity.models import ActivityEntry


class ActivityRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, project_id: int, message: str, *, level: str = "info", job_id: int | None = None,
            image_id: int | None = None) -> ActivityEntry:
        entry = ActivityEntry(project_id=project_id, message=message, level=level, job_id=job_id, image_id=image_id)
        self.session.add(entry)
        self.session.flush()
        self.session.refresh(entry)
        return entry

    def get(self, entry_id: int) -> ActivityEntry | None:
        return self.session.get(ActivityEntry, entry_id)

    def list_recent(self, project_id: int, limit: int) -> list[ActivityEntry]:
        stmt = (select(ActivityEntry).where(ActivityEntry.project_id == project_id)
                .order_by(ActivityEntry.id.desc()).limit(limit))
        return list(self.session.scalars(stmt))
