from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from annotator.classes.repository import ClassRepository
from annotator.classes.service import ClassService
from annotator.db.session import get_session
from annotator.health.schemas import HealthReport
from annotator.health.service import HealthService
from annotator.image.repository import ImageRepository
from annotator.image.service import ImageService
from annotator.label.repository import LabelRepository
from annotator.label.service import LabelService
from annotator.project.repository import ProjectRepository
from annotator.project.service import ProjectService
from annotator.storage.dependencies import get_storage
from annotator.storage.storage_service import StorageService

router = APIRouter(prefix="/api/projects/{project_id}/health", tags=["health"])


def get_health_service(session: Session = Depends(get_session),
                       storage: StorageService = Depends(get_storage)) -> HealthService:
    projects = ProjectService(ProjectRepository(session))
    images = ImageService(ImageRepository(session), storage, projects)
    classes = ClassService(ClassRepository(session), projects)
    return HealthService(images, classes, LabelService(LabelRepository(session), images, classes))


@router.get("", response_model=HealthReport)
def get_health(project_id: int, low: int = 100, service: HealthService = Depends(get_health_service)):
    return service.report(project_id, low)
