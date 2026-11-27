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
from tests.fakes import (
    FakeClassRepository,
    FakeImageRepository,
    FakeLabelRepository,
    FakeProjectRepository,
    FakeStorage,
)

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
    assert out["boxes"] == [{"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5, "source": "human", "conf": None, "points": None}]


def test_put_with_an_old_version_is_problem_409(client):
    body = {"boxes": [], "status": "edited", "expectedUpdatedAt": "2026-11-22T00:00:00Z"}
    r = client.put("/api/images/1/boxes", json=body)
    assert (r.status_code, r.json()["code"]) == (409, "STALE_IMAGE")


def test_the_editor_saves_only_as_edited_or_reviewed(client):
    r = client.put("/api/images/1/boxes", json={"boxes": [], "status": "auto", "expectedUpdatedAt": STAMP})
    assert (r.status_code, r.json()["code"]) == (400, "VALIDATION_FAILED")
    assert [e["field"] for e in r.json()["errors"]] == ["status"]


def test_the_docs_list_the_save_statuses(client):
    props = client.get("/openapi.json").json()["components"]["schemas"]["SaveBoxes"]["properties"]
    assert props["status"]["enum"] == ["edited", "reviewed"]


def test_flag_and_unflag(client):
    r = client.put("/api/images/1/flag", json={"flagged": True, "reason": "unsure", "note": "left can"})
    assert (r.json()["flagged"], r.json()["flagReason"], r.json()["flagNote"]) == (True, "unsure", "left can")
    r = client.put("/api/images/1/flag", json={"flagged": False})
    assert (r.json()["flagged"], r.json()["flagReason"]) == (False, "")


def test_put_and_get_round_trip_an_outline(client):
    outline = {"cls": 0, "x1": 0, "y1": 0, "x2": 1, "y2": 1, "points": [[0.2, 0.1], [0.6, 0.3], [0.3, 0.7]]}
    plain = {"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5}
    r = client.put("/api/images/1/boxes", json={"boxes": [outline, plain], "status": "edited", "expectedUpdatedAt": STAMP})
    assert r.status_code == 200
    boxes = client.get("/api/images/1/boxes").json()["boxes"]
    assert [b["points"] for b in boxes] == [[[0.2, 0.1], [0.6, 0.3], [0.3, 0.7]], None]
    assert (boxes[0]["x1"], boxes[0]["y2"]) == (0.2, 0.7)


def test_more_than_1000_dots_is_validation_failed(client):
    dots = [[0.1 + i * 0.0001, 0.2 + (i % 2) * 0.1] for i in range(1001)]
    body = {"boxes": [{"cls": 0, "x1": 0, "y1": 0, "x2": 1, "y2": 1, "points": dots}], "status": "edited",
            "expectedUpdatedAt": STAMP}
    r = client.put("/api/images/1/boxes", json=body)
    assert (r.status_code, r.json()["code"]) == (400, "VALIDATION_FAILED")
