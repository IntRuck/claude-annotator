from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from annotator.db.session import get_session
from annotator.image.repository import ImageRepository
from annotator.image.schemas import ImageList, ImageOut, UploadResult
from annotator.image.service import SIGNED_URL_SECONDS, ImageService, UploadedFile
from annotator.project.repository import ProjectRepository
from annotator.project.service import ProjectService
from annotator.storage.dependencies import get_storage
from annotator.storage.storage_service import StorageService

router = APIRouter(prefix="/api", tags=["images"])

# The browser may reuse a redirect a bit less long than the signed link lives.
_REDIRECT_CACHE = f"private, max-age={SIGNED_URL_SECONDS - 300}"


def get_image_service(session: Session = Depends(get_session),
                      storage: StorageService = Depends(get_storage)) -> ImageService:
    return ImageService(ImageRepository(session), storage, ProjectService(ProjectRepository(session)))


@router.post("/projects/{project_id}/images", response_model=UploadResult, status_code=201)
def upload_images(project_id: int, files: list[UploadFile] = File(...),
                  service: ImageService = Depends(get_image_service)):
    uploads = [UploadedFile(f.filename or "", f.file.read(), f.content_type or "") for f in files]
    return service.upload(project_id, uploads)


@router.get("/projects/{project_id}/images", response_model=ImageList)
def list_images(project_id: int, filter: str = "all", service: ImageService = Depends(get_image_service)):
    return service.list_images(project_id, filter)


@router.get("/images/{image_id}", response_model=ImageOut)
def get_image(image_id: int, service: ImageService = Depends(get_image_service)):
    return service.get_image(image_id)


@router.get("/images/{image_id}/thumb")
def image_thumb(image_id: int, service: ImageService = Depends(get_image_service)):
    return RedirectResponse(service.thumb_url(image_id), status_code=302, headers={"Cache-Control": _REDIRECT_CACHE})


@router.get("/images/{image_id}/file")
def image_file(image_id: int, service: ImageService = Depends(get_image_service)):
    return RedirectResponse(service.file_url(image_id), status_code=302, headers={"Cache-Control": _REDIRECT_CACHE})
