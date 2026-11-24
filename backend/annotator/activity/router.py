from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from annotator.activity.repository import ActivityRepository
from annotator.activity.schemas import ActivityOut
from annotator.activity.service import ActivityService
from annotator.db.session import get_session
from annotator.project.repository import ProjectRepository
from annotator.project.service import ProjectService

router = APIRouter(prefix="/api/projects/{project_id}/activity", tags=["activity"])


def get_activity_service(session: Session = Depends(get_session)) -> ActivityService:
    return ActivityService(ActivityRepository(session), ProjectService(ProjectRepository(session)))


@router.get("", response_model=list[ActivityOut])
def list_activity(project_id: int, limit: int = 100, service: ActivityService = Depends(get_activity_service)):
    return service.list_recent(project_id, limit)
