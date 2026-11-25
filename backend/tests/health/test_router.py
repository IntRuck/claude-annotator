from fastapi.testclient import TestClient

from annotator.health.router import get_health_service
from annotator.main import create_app


def client(service):
    app = create_app()
    app.dependency_overrides[get_health_service] = lambda: service
    return TestClient(app)


def test_get_health_returns_the_report(service):
    r = client(service).get("/api/projects/1/health?low=5")
    assert r.status_code == 200
    assert r.json()["lowCount"] == 5
    assert r.json()["summary"]["images"] == 2


def test_warn_below_defaults_to_100(service):
    assert client(service).get("/api/projects/1/health").json()["lowCount"] == 100


def test_bad_warn_below_is_problem_json(service):
    r = client(service).get("/api/projects/1/health?low=0")
    assert r.status_code == 400
    assert r.json()["code"] == "BAD_LOW_COUNT"


def test_missing_project_is_404(service):
    assert client(service).get("/api/projects/42/health").json()["code"] == "PROJECT_NOT_FOUND"
