import pytest
from fastapi.testclient import TestClient

from annotator.main import create_app
from annotator.project.router import get_project_service
from annotator.project.service import ProjectService
from tests.fakes import FakeProjectRepository


@pytest.fixture
def client():
    app = create_app()
    service = ProjectService(FakeProjectRepository())
    app.dependency_overrides[get_project_service] = lambda: service
    return TestClient(app)


def test_create_project_returns_201_with_camel_case_fields(client):
    r = client.post("/api/projects", json={"name": "Shelf"})
    assert r.status_code == 201
    assert r.json() == {"id": 1, "name": "Shelf", "createdAt": "2026-11-23T00:00:00Z"}


def test_create_project_blank_name_is_problem_400(client):
    r = client.post("/api/projects", json={"name": " "})
    assert r.status_code == 400
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == "PROJECT_NAME_REQUIRED"


def test_create_project_without_name_is_validation_failed(client):
    r = client.post("/api/projects", json={})
    assert (r.status_code, r.json()["code"]) == (400, "VALIDATION_FAILED")


def test_list_and_get_projects(client):
    client.post("/api/projects", json={"name": "First"})
    client.post("/api/projects", json={"name": "Second"})
    assert [p["name"] for p in client.get("/api/projects").json()] == ["Second", "First"]
    assert client.get("/api/projects/1").json()["name"] == "First"


def test_get_missing_project_is_problem_404(client):
    r = client.get("/api/projects/9")
    assert (r.status_code, r.json()["code"]) == (404, "PROJECT_NOT_FOUND")
