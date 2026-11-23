from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from annotator.classes.repository import ClassRepository
from annotator.classes.schemas import ClassCreate, ClassOut, ClassUpdate
from annotator.classes.service import ClassService
from annotator.db.session import get_session
from annotator.project.repository import ProjectRepository
from annotator.project.service import ProjectService

router = APIRouter(prefix="/api/projects/{project_id}/classes", tags=["classes"])


def get_class_service(session: Session = Depends(get_session)) -> ClassService:
    return ClassService(ClassRepository(session), ProjectService(ProjectRepository(session)))


@router.get("", response_model=list[ClassOut])
def list_classes(project_id: int, service: ClassService = Depends(get_class_service)):
    return service.list_classes(project_id)


@router.post("", response_model=ClassOut, status_code=201)
def add_class(project_id: int, body: ClassCreate, service: ClassService = Depends(get_class_service)):
    return service.add_class(project_id, body)


@router.patch("/{class_index}", response_model=ClassOut)
def update_class(project_id: int, class_index: int, body: ClassUpdate,
                 service: ClassService = Depends(get_class_service)):
    return service.update_class(project_id, class_index, body)
