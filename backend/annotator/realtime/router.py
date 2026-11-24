from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from annotator.db.session import get_session
from annotator.project.repository import ProjectRepository
from annotator.project.service import ProjectService
from annotator.realtime.broadcaster import Broadcaster
from annotator.realtime.dependencies import get_broadcaster
from annotator.realtime.service import EventStreamService
from annotator.realtime.sse import event_stream

router = APIRouter(prefix="/api/projects/{project_id}/events", tags=["realtime"])


# scope="function": the session is closed as soon as the project check is done, not when the stream ends,
# so an open tab doesn't hold a database connection.
def get_event_stream_service(session: Session = Depends(get_session, scope="function"),
                             broadcaster: Broadcaster = Depends(get_broadcaster)) -> EventStreamService:
    return EventStreamService(ProjectService(ProjectRepository(session)), broadcaster)


# async: subscribing touches the broadcaster, which belongs to the event loop.
@router.get("", response_class=StreamingResponse)
async def events(project_id: int, service: EventStreamService = Depends(get_event_stream_service, scope="function")):
    subscription = service.open(project_id)
    return StreamingResponse(event_stream(subscription), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
