from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from annotator.db.session import get_session
from annotator.project.repository import ProjectRepository
from annotator.project.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from annotator.project.service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])

# DELETE /api/projects/{id} lives in overview/router.py: it also removes the project's photo files, which
# belong to the image feature (and ImageService already depends on ProjectService).


def get_project_service(session: Session = Depends(get_session)) -> ProjectService:
    return ProjectService(ProjectRepository(session))


@router.get("", response_model=list[ProjectOut])
def list_projects(service: ProjectService = Depends(get_project_service)):
    return service.list_projects()


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, service: ProjectService = Depends(get_project_service)):
    return service.create_project(body.name, body.description)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, service: ProjectService = Depends(get_project_service)):
    return service.get_project(project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, body: ProjectUpdate, service: ProjectService = Depends(get_project_service)):
    return service.update_project(project_id, name=body.name, description=body.description)
