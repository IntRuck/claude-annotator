from fastapi.testclient import TestClient

from annotator.activity.router import get_activity_service
from annotator.activity.service import ActivityService
from annotator.main import create_app
from annotator.project.service import ProjectService
from tests.fakes import FakeActivityRepository, FakeProjectRepository


def client():
    app = create_app()
    projects = ProjectService(FakeProjectRepository())
    projects.create_project("Shelf")
    activity = ActivityService(FakeActivityRepository(), projects)
    for n in range(3):
        activity.log(1, f"line {n}")
    app.dependency_overrides[get_activity_service] = lambda: activity
    return TestClient(app)


def test_get_activity_returns_recent_entries_newest_first():
    r = client().get("/api/projects/1/activity?limit=2")
    assert r.status_code == 200
    assert [e["message"] for e in r.json()] == ["line 2", "line 1"]


def test_default_limit_is_100():
    assert len(client().get("/api/projects/1/activity").json()) == 3


def test_bad_limit_is_problem_json():
    assert client().get("/api/projects/1/activity?limit=0").json()["code"] == "BAD_LIMIT"
