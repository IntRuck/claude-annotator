from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from annotator.classes.repository import ClassRepository
from annotator.classes.service import ClassService
from annotator.db.session import get_session
from annotator.image.repository import ImageRepository
from annotator.image.service import ImageService
from annotator.overview.schemas import ProjectSummary
from annotator.overview.service import OverviewService
from annotator.project.repository import ProjectRepository
from annotator.project.service import ProjectService
from annotator.storage.dependencies import get_storage
from annotator.storage.storage_service import StorageService

router = APIRouter(prefix="/api", tags=["overview"])


def get_overview_service(session: Session = Depends(get_session),
                         storage: StorageService = Depends(get_storage)) -> OverviewService:
    projects = ProjectService(ProjectRepository(session))
    return OverviewService(projects, ImageService(ImageRepository(session), storage, projects),
                           ClassService(ClassRepository(session), projects))


# Not /api/projects/summary: GET /api/projects/{project_id} would catch that path first.
@router.get("/project-summaries", response_model=list[ProjectSummary])
def project_summaries(service: OverviewService = Depends(get_overview_service)):
    return service.summaries()


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: int, service: OverviewService = Depends(get_overview_service)):
    service.delete_project(project_id)
    return Response(status_code=204)
