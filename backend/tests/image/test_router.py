import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from annotator.image.router import get_image_service
from annotator.image.service import ImageService
from annotator.main import create_app
from annotator.project.service import ProjectService
from tests.fakes import FakeImageRepository, FakeProjectRepository, FakeStorage


def jpg():
    buf = io.BytesIO()
    Image.new("RGB", (64, 32)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def client():
    app = create_app()
    projects = ProjectService(FakeProjectRepository())
    projects.create_project("Shelf")
    service = ImageService(FakeImageRepository(), FakeStorage(), projects)
    app.dependency_overrides[get_image_service] = lambda: service
    return TestClient(app, follow_redirects=False)


def test_multipart_upload_returns_added_and_skipped(client):
    files = [("files", ("a.jpg", jpg(), "image/jpeg")), ("files", ("notes.txt", b"hi", "text/plain"))]
    r = client.post("/api/projects/1/images", files=files)
    assert r.status_code == 201
    body = r.json()
    assert [a["fileName"] for a in body["added"]] == ["a.jpg"]
    assert body["added"][0]["width"] == 64 and body["added"][0]["status"] == "unlabeled"
    assert body["skipped"] == [{"fileName": "notes.txt", "reason": "not a supported image type (jpg, jpeg, png, bmp, webp)"}]


def test_list_images_with_filter_and_counts(client):
    client.post("/api/projects/1/images", files=[("files", ("a.jpg", jpg(), "image/jpeg"))])
    body = client.get("/api/projects/1/images", params={"filter": "unlabeled"}).json()
    assert [i["fileName"] for i in body["items"]] == ["a.jpg"]
    assert body["counts"]["all"] == 1
    assert set(body["items"][0]) >= {"id", "fileName", "width", "height", "status", "note", "flagged", "flagReason", "flagNote", "boxCount", "updatedAt"}


def test_list_defaults_to_all_and_rejects_unknown_filter(client):
    assert client.get("/api/projects/1/images").status_code == 200
    r = client.get("/api/projects/1/images", params={"filter": "pink"})
    assert (r.status_code, r.json()["code"]) == (400, "VALIDATION_FAILED")
    assert [e["field"] for e in r.json()["errors"]] == ["filter"]


def test_the_docs_list_the_filters(client):
    params = client.get("/openapi.json").json()["paths"]["/api/projects/{project_id}/images"]["get"]["parameters"]
    (flt,) = [p for p in params if p["name"] == "filter"]
    assert flt["schema"]["enum"] == ["all", "unlabeled", "auto", "edited", "reviewed", "flagged", "error"]


def test_get_one_image(client):
    client.post("/api/projects/1/images", files=[("files", ("a.jpg", jpg(), "image/jpeg"))])
    assert client.get("/api/images/1").json()["fileName"] == "a.jpg"
    assert client.get("/api/images/9").json()["code"] == "IMAGE_NOT_FOUND"


@pytest.mark.parametrize("kind", ["thumb", "file"])
def test_thumb_and_file_redirect_to_a_signed_url_the_browser_can_cache(client, kind):
    client.post("/api/projects/1/images", files=[("files", ("a.jpg", jpg(), "image/jpeg"))])
    r = client.get(f"/api/images/1/{kind}")
    assert r.status_code == 302
    assert r.headers["location"].startswith("http://storage.test/images/1/")
    assert r.headers["cache-control"] == "private, max-age=3300"
