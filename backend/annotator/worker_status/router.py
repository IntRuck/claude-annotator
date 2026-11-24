from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from annotator.db.session import get_session
from annotator.worker_status.repository import WorkerStatusRepository
from annotator.worker_status.schemas import EngineStatus, ResumeResult
from annotator.worker_status.service import WorkerStatusService

router = APIRouter(prefix="/api", tags=["worker"])


def get_worker_status_service(session: Session = Depends(get_session)) -> WorkerStatusService:
    return WorkerStatusService(WorkerStatusRepository(session))


@router.get("/engines", response_model=EngineStatus)
def engine_status(service: WorkerStatusService = Depends(get_worker_status_service)):
    return service.status()


@router.post("/worker/resume", response_model=ResumeResult)
def resume(service: WorkerStatusService = Depends(get_worker_status_service)):
    return service.resume()
