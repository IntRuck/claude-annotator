import pytest
from fastapi.testclient import TestClient

from annotator.classes.schemas import ClassCreate
from annotator.classes.service import ClassService
from annotator.image.router import get_image_service
from annotator.image.service import ImageService
from annotator.label.router import get_label_service
from annotator.label.service import LabelService
from annotator.main import create_app
from annotator.project.service import ProjectService
from tests.fakes import FakeClassRepository, FakeImageRepository, FakeLabelRepository, FakeProjectRepository, FakeStorage

STAMP = "2026-11-23T00:00:00Z"


@pytest.fixture
def client():
    app = create_app()
    projects = ProjectService(FakeProjectRepository())
    projects.create_project("Shelf")
    classes = ClassService(FakeClassRepository(), projects)
    classes.add_class(1, ClassCreate(name="can"))
    images_repo = FakeImageRepository()
    images_repo.add(1, file_name="a.jpg", stem="a", storage_path="p", thumb_path="t", width=100, height=50)
    images = ImageService(images_repo, FakeStorage(), projects)
    labels = LabelService(FakeLabelRepository(images_repo), images, classes)
    app.dependency_overrides[get_label_service] = lambda: labels
    app.dependency_overrides[get_image_service] = lambda: images
    return TestClient(app)


def test_get_boxes_returns_boxes_and_the_version_to_send_back(client):
    assert client.get("/api/images/1/boxes").json() == {"boxes": [], "updatedAt": STAMP}


def test_put_boxes_saves_and_returns_the_image_and_boxes(client):
    body = {"boxes": [{"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5}], "status": "reviewed", "expectedUpdatedAt": STAMP}
    r = client.put("/api/images/1/boxes", json=body)
    assert r.status_code == 200
    out = r.json()
    assert (out["image"]["status"], out["image"]["boxCount"]) == ("reviewed", 1)
    assert out["boxes"] == [{"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5, "source": "human", "conf": None}]


def test_put_with_an_old_version_is_problem_409(client):
    body = {"boxes": [], "status": "edited", "expectedUpdatedAt": "2026-11-22T00:00:00Z"}
    r = client.put("/api/images/1/boxes", json=body)
    assert (r.status_code, r.json()["code"]) == (409, "STALE_IMAGE")


def test_flag_and_unflag(client):
    r = client.put("/api/images/1/flag", json={"flagged": True, "reason": "unsure", "note": "left can"})
    assert (r.json()["flagged"], r.json()["flagReason"], r.json()["flagNote"]) == (True, "unsure", "left can")
    r = client.put("/api/images/1/flag", json={"flagged": False})
    assert (r.json()["flagged"], r.json()["flagReason"]) == (False, "")
