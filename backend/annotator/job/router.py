from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from annotator.activity.repository import ActivityRepository
from annotator.activity.service import ActivityService
from annotator.classes.repository import ClassRepository
from annotator.classes.service import ClassService
from annotator.db.session import get_session
from annotator.image.repository import ImageRepository
from annotator.image.service import ImageService
from annotator.job.repository import JobRepository
from annotator.job.schemas import JobCreate, JobSummary, QueueResult, StopResult
from annotator.job.service import JobService
from annotator.label.repository import LabelRepository
from annotator.label.service import LabelService
from annotator.project.repository import ProjectRepository
from annotator.project.service import ProjectService
from annotator.storage.dependencies import get_storage
from annotator.storage.storage_service import StorageService

router = APIRouter(prefix="/api/projects/{project_id}/jobs", tags=["jobs"])


def get_job_service(session: Session = Depends(get_session),
                    storage: StorageService = Depends(get_storage)) -> JobService:
    projects = ProjectService(ProjectRepository(session))
    images = ImageService(ImageRepository(session), storage, projects)
    classes = ClassService(ClassRepository(session), projects)
    return JobService(JobRepository(session), projects, images, classes,
                      ActivityService(ActivityRepository(session), projects),
                      LabelService(LabelRepository(session), images, classes))


@router.post("", response_model=QueueResult, status_code=202)
def queue_jobs(project_id: int, body: JobCreate, service: JobService = Depends(get_job_service)):
    return service.queue(project_id, body)


@router.post("/stop", response_model=StopResult)
def stop_jobs(project_id: int, service: JobService = Depends(get_job_service)):
    return service.stop(project_id)


@router.get("/summary", response_model=JobSummary)
def job_summary(project_id: int, service: JobService = Depends(get_job_service)):
    return service.summary(project_id)
