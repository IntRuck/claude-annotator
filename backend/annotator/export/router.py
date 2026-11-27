import json
import os
import tempfile

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from annotator.classes.repository import ClassRepository
from annotator.classes.service import ClassService
from annotator.db.session import get_session
from annotator.export.schemas import ExportSummary, Shape
from annotator.export.service import ExportService
from annotator.image.repository import ImageRepository
from annotator.image.service import ImageService
from annotator.label.repository import LabelRepository
from annotator.label.service import LabelService
from annotator.project.repository import ProjectRepository
from annotator.project.service import ProjectService
from annotator.storage.dependencies import get_storage
from annotator.storage.storage_service import StorageService

router = APIRouter(prefix="/api/projects/{project_id}/exports", tags=["export"])

OnlyReviewed = Query(False, alias="onlyReviewed")
SkipFlagged = Query(True, alias="skipFlagged")
ShapeQuery = Query("boxes")
# Outline files get their own names, so they don't overwrite a box export in the Downloads folder.
YOLO_NAMES = {"boxes": "yolo_dataset.zip", "outlines": "yolo_seg_dataset.zip"}
COCO_NAMES = {"boxes": "annotations_coco.json", "outlines": "annotations_coco_seg.json"}


def get_export_service(session: Session = Depends(get_session),
                       storage: StorageService = Depends(get_storage)) -> ExportService:
    projects = ProjectService(ProjectRepository(session))
    images = ImageService(ImageRepository(session), storage, projects)
    classes = ClassService(ClassRepository(session), projects)
    return ExportService(images, classes, LabelService(LabelRepository(session), images, classes))


@router.get("/summary", response_model=ExportSummary)
def export_summary(project_id: int, only_reviewed: bool = OnlyReviewed, skip_flagged: bool = SkipFlagged,
                   shape: Shape = ShapeQuery, service: ExportService = Depends(get_export_service)):
    return service.summary(project_id, only_reviewed, skip_flagged, shape)


@router.get("/yolo", response_class=FileResponse)
def download_yolo(project_id: int, only_reviewed: bool = OnlyReviewed, skip_flagged: bool = SkipFlagged,
                  shape: Shape = ShapeQuery, service: ExportService = Depends(get_export_service)):
    """The zip is written to a temp file (it holds every photo, so not in memory), sent, then deleted."""
    fd, path = tempfile.mkstemp(prefix="annotator-yolo-", suffix=".zip")
    try:
        with os.fdopen(fd, "wb") as out:
            service.write_yolo(project_id, out, only_reviewed, skip_flagged, shape)
    except BaseException:
        os.remove(path)
        raise
    return FileResponse(path, media_type="application/zip", filename=YOLO_NAMES[shape],
                        background=BackgroundTask(os.remove, path))


@router.get("/coco")
def download_coco(project_id: int, only_reviewed: bool = OnlyReviewed, skip_flagged: bool = SkipFlagged,
                  shape: Shape = ShapeQuery, service: ExportService = Depends(get_export_service)):
    body = json.dumps(service.coco(project_id, only_reviewed, skip_flagged, shape), indent=1)
    return Response(body, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{COCO_NAMES[shape]}"'})
