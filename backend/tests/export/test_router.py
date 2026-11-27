import io
import tempfile
import zipfile

import pytest
from fastapi.testclient import TestClient

from annotator.export.router import get_export_service
from annotator.main import create_app


@pytest.fixture
def client(service, tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))  # the zip is built in a temp file; see it removed
    app = create_app()
    app.dependency_overrides[get_export_service] = lambda: service
    return TestClient(app)


def test_summary_counts_what_would_go_in(client):
    assert client.get("/api/projects/1/exports/summary").json() == {"images": 2, "boxes": 3, "train": 2, "val": 0, "leftOut": 0}
    assert client.get("/api/projects/1/exports/summary?skipFlagged=false").json()["images"] == 3
    assert client.get("/api/projects/1/exports/summary?onlyReviewed=true").json()["images"] == 1


def test_yolo_downloads_a_zip_and_removes_the_temp_file(client, tmp_path):
    r = client.get("/api/projects/1/exports/yolo?skipFlagged=false")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert 'attachment; filename="yolo_dataset.zip"' in r.headers["content-disposition"]
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert "dataset/images/train/c.jpg" in names and "dataset/data.yaml" in names
    assert list(tmp_path.iterdir()) == []


def test_coco_downloads_a_json_file(client):
    r = client.get("/api/projects/1/exports/coco?onlyReviewed=true")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert 'attachment; filename="annotations_coco.json"' in r.headers["content-disposition"]
    assert [i["file_name"] for i in r.json()["images"]] == ["b.jpg"]


def test_missing_project_is_problem_json_and_leaves_no_temp_file(client, tmp_path):
    for kind in ("summary", "yolo", "coco"):
        r = client.get(f"/api/projects/42/exports/{kind}")
        assert (r.status_code, r.json()["code"]) == (404, "PROJECT_NOT_FOUND")
    assert list(tmp_path.iterdir()) == []



def test_outline_downloads_are_named_for_segmentation(client):
    r = client.get("/api/projects/1/exports/yolo?shape=outlines")
    assert 'attachment; filename="yolo_seg_dataset.zip"' in r.headers["content-disposition"]
    r = client.get("/api/projects/1/exports/coco?shape=outlines")
    assert 'attachment; filename="annotations_coco_seg.json"' in r.headers["content-disposition"]


def test_unknown_shape_is_validation_failed_and_the_docs_list_the_shapes(client):
    r = client.get("/api/projects/1/exports/summary?shape=masks")
    assert (r.status_code, r.json()["code"]) == (400, "VALIDATION_FAILED")
    params = client.get("/openapi.json").json()["paths"]["/api/projects/{project_id}/exports/summary"]["get"]["parameters"]
    assert next(p for p in params if p["name"] == "shape")["schema"]["enum"] == ["boxes", "outlines"]
