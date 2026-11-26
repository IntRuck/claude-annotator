"""GET /api/projects/{id}/events: the SSE stream one browser tab keeps open."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from annotator.db.session import get_session
from annotator.main import create_app
from annotator.project.models import Project
from annotator.project.service import ProjectService
from annotator.realtime.broadcaster import Broadcaster
from annotator.realtime.dependencies import get_broadcaster
from annotator.realtime.router import get_event_stream_service
from annotator.realtime.service import EventStreamService
from tests.fakes import FakeProjectRepository


class ScriptedBroadcaster(Broadcaster):
    """Queues the given messages for the new stream, then ends it (TestClient waits for the whole body)."""

    def __init__(self, messages, on_first_get=None):
        super().__init__()
        self.messages = messages
        self.on_first_get = on_first_get

    def subscribe(self, project_id):
        sub = super().subscribe(project_id)
        for m in self.messages:
            self.publish(project_id, m)
        self.shutdown()
        if self.on_first_get:
            original = sub.get

            async def get():
                self.on_first_get()
                return await original()

            sub.get = get
        return sub


def client_with(broadcaster):
    app = create_app()
    projects = ProjectService(FakeProjectRepository())
    projects.create_project("Shelf")
    app.dependency_overrides[get_event_stream_service] = lambda: EventStreamService(projects, broadcaster)
    return TestClient(app)


def test_stream_sends_messages_of_the_project_as_server_sent_events():
    msg = {"type": "images", "op": "update", "data": {"id": 1}}
    r = client_with(ScriptedBroadcaster([msg])).get("/api/projects/1/events")

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["cache-control"] == "no-cache"
    assert r.headers["x-accel-buffering"] == "no"
    assert r.text == 'retry: 3000\n\ndata: {"type":"images","op":"update","data":{"id":1}}\n\n'


def test_unknown_project_is_404_problem_json():
    r = client_with(ScriptedBroadcaster([])).get("/api/projects/42/events")
    assert r.status_code == 404
    assert r.json()["code"] == "PROJECT_NOT_FOUND"


class OneProjectSession:
    """Just enough of a SQLAlchemy session for ProjectRepository.get."""

    def get(self, model, project_id):
        when = datetime(2026, 11, 23, tzinfo=timezone.utc)
        return Project(id=project_id, name="Shelf", description="", created_at=when, updated_at=when)


def test_the_database_session_is_released_before_streaming_starts():
    """An open tab must not hold a database connection for as long as it stays open."""
    state = {"closed": False, "closed_when_streaming": None}

    def recording_session():
        try:
            yield OneProjectSession()
        finally:
            state["closed"] = True

    def first_get():
        state["closed_when_streaming"] = state["closed"]

    app = create_app()
    app.dependency_overrides[get_session] = recording_session
    app.dependency_overrides[get_broadcaster] = lambda: ScriptedBroadcaster([], on_first_get=first_get)

    r = TestClient(app).get("/api/projects/1/events")

    assert r.status_code == 200
    assert state["closed_when_streaming"] is True
