from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from annotator.classes.repository import ClassRepository
from annotator.classes.service import ClassService
from annotator.db.session import get_session
from annotator.image.repository import ImageRepository
from annotator.image.service import ImageService
from annotator.label.repository import LabelRepository
from annotator.label.schemas import ImageBoxes, SaveBoxes, SaveResult
from annotator.label.service import LabelService
from annotator.project.repository import ProjectRepository
from annotator.project.service import ProjectService
from annotator.storage.dependencies import get_storage
from annotator.storage.storage_service import StorageService

router = APIRouter(prefix="/api/images/{image_id}/boxes", tags=["labels"])


def get_label_service(session: Session = Depends(get_session),
                      storage: StorageService = Depends(get_storage)) -> LabelService:
    projects = ProjectService(ProjectRepository(session))
    images = ImageService(ImageRepository(session), storage, projects)
    return LabelService(LabelRepository(session), images, ClassService(ClassRepository(session), projects))


@router.get("", response_model=ImageBoxes)
def get_boxes(image_id: int, service: LabelService = Depends(get_label_service)):
    return service.get_boxes(image_id)


@router.put("", response_model=SaveResult)
def save_boxes(image_id: int, body: SaveBoxes, service: LabelService = Depends(get_label_service)):
    return service.save(image_id, body)
