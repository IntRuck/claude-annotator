import pytest
from fastapi.testclient import TestClient

from annotator.classes.router import get_class_service
from annotator.classes.service import ClassService
from annotator.main import create_app
from annotator.project.service import ProjectService
from tests.fakes import FakeClassRepository, FakeProjectRepository


@pytest.fixture
def client():
    app = create_app()
    projects = ProjectService(FakeProjectRepository())
    projects.create_project("Shelf")
    service = ClassService(FakeClassRepository(), projects)
    app.dependency_overrides[get_class_service] = lambda: service
    return TestClient(app)


def test_add_class_returns_201_with_index_and_camel_case(client):
    r = client.post("/api/projects/1/classes",
                    json={"name": "tuna 400g", "detectorPrompt": "red tin", "description": "Short red tin"})
    assert r.status_code == 201
    assert r.json() == {"index": 0, "name": "tuna_400g", "detectorPrompt": "red tin", "description": "Short red tin"}


def test_list_classes_in_index_order(client):
    for name in ("can", "bottle"):
        client.post("/api/projects/1/classes", json={"name": name})
    assert [(c["index"], c["name"]) for c in client.get("/api/projects/1/classes").json()] == [(0, "can"), (1, "bottle")]


def test_patch_changes_only_the_fields_sent(client):
    client.post("/api/projects/1/classes", json={"name": "can", "detectorPrompt": "metal can"})
    r = client.patch("/api/projects/1/classes/0", json={"description": "Silver"})
    assert r.status_code == 200
    assert r.json() == {"index": 0, "name": "can", "detectorPrompt": "metal can", "description": "Silver"}


def test_taken_name_is_problem_409(client):
    client.post("/api/projects/1/classes", json={"name": "can"})
    r = client.post("/api/projects/1/classes", json={"name": "Can"})
    assert (r.status_code, r.json()["code"]) == (409, "CLASS_NAME_TAKEN")


def test_missing_project_and_missing_class_are_404(client):
    assert client.get("/api/projects/9/classes").json()["code"] == "PROJECT_NOT_FOUND"
    assert client.patch("/api/projects/1/classes/3", json={"name": "x"}).json()["code"] == "CLASS_NOT_FOUND"
