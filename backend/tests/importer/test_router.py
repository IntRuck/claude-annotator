import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from annotator.classes.service import ClassService
from annotator.image.service import ImageService
from annotator.importer.router import get_import_service
from annotator.importer.service import ImportService
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


def jpg():
    buf = io.BytesIO()
    Image.new("RGB", (100, 50)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def client():
    app = create_app()
    projects = ProjectService(FakeProjectRepository())
    projects.create_project("Shelf")
    images_repo = FakeImageRepository()
    images = ImageService(images_repo, FakeStorage(), projects)
    classes = ClassService(FakeClassRepository(), projects)
    service = ImportService(images, classes, LabelService(FakeLabelRepository(images_repo), images, classes))
    app.dependency_overrides[get_import_service] = lambda: service
    return TestClient(app)


def test_import_takes_a_folder_of_files_with_their_paths(client):
    files = [
        ("files", ("shelf/images/a.jpg", jpg(), "image/jpeg")),
        ("files", ("shelf/labels/a.txt", b"0 0.5 0.5 0.2 0.2\n", "text/plain")),
        ("files", ("shelf/labels/_annot_state.json", json.dumps({"a.jpg": {"status": "reviewed"}}).encode(), "application/json")),
        ("files", ("shelf/classes.txt", b"can\n", "text/plain")),
    ]
    r = client.post("/api/projects/1/import", files=files)
    assert r.status_code == 200
    body = r.json()
    assert (body["added"], body["labelled"], body["boxes"], body["statesApplied"]) == (1, 1, 1, 1)
    assert body["classesCreated"] == ["can"]
    assert set(body) >= {"skipped", "placeholderClasses", "keptExistingClasses", "labelsWithoutImage",
                         "badLabelLines", "ignoredFiles", "warnings"}


def test_import_into_a_missing_project_is_404(client):
    r = client.post("/api/projects/9/import", files=[("files", ("a.jpg", jpg(), "image/jpeg"))])
    assert (r.status_code, r.json()["code"]) == (404, "PROJECT_NOT_FOUND")
