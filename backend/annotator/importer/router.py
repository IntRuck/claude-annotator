from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from annotator.classes.repository import ClassRepository
from annotator.classes.service import ClassService
from annotator.db.session import get_session
from annotator.image.repository import ImageRepository
from annotator.image.service import ImageService, UploadedFile
from annotator.importer.schemas import ImportResult
from annotator.importer.service import ImportService
from annotator.label.repository import LabelRepository
from annotator.label.service import LabelService
from annotator.project.repository import ProjectRepository
from annotator.project.service import ProjectService
from annotator.storage.dependencies import get_storage
from annotator.storage.storage_service import StorageService

router = APIRouter(prefix="/api/projects/{project_id}/import", tags=["import"])


def get_import_service(session: Session = Depends(get_session),
                       storage: StorageService = Depends(get_storage)) -> ImportService:
    projects = ProjectService(ProjectRepository(session))
    images = ImageService(ImageRepository(session), storage, projects)
    classes = ClassService(ClassRepository(session), projects)
    return ImportService(images, classes, LabelService(LabelRepository(session), images, classes))


@router.post("", response_model=ImportResult)
def import_dataset(project_id: int, files: list[UploadFile] = File(...),
                   service: ImportService = Depends(get_import_service)):
    """Files keep their folder path in the file name (the browser sends it when a folder is picked)."""
    uploads = [UploadedFile(f.filename or "", f.file.read(), f.content_type or "") for f in files]
    return service.import_dataset(project_id, uploads)
