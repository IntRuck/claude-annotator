"""Whole stack against real Postgres: router -> service -> repository -> Flyway schema -> JSON.
Storage is faked (it has its own check against the real local Storage)."""
import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from annotator.db.session import get_session
from annotator.main import create_app
from annotator.storage.dependencies import get_storage
from tests.fakes import FakeStorage

pytestmark = pytest.mark.db


@pytest.fixture
def client(db_session):
    app = create_app()

    def session_in_test_transaction():
        yield db_session
        db_session.flush()

    app.dependency_overrides[get_session] = session_in_test_transaction
    app.dependency_overrides[get_storage] = FakeStorage
    return TestClient(app)


def test_project_and_sku_flow(client):
    project = client.post("/api/projects", json={"name": "Shelf scans"}).json()
    pid = project["id"]

    assert client.post(f"/api/projects/{pid}/classes", json={"name": "tuna 400g", "description": "Red\ntin"}).status_code == 201
    assert client.post(f"/api/projects/{pid}/classes", json={"name": "bottle"}).json()["index"] == 1

    taken = client.post(f"/api/projects/{pid}/classes", json={"name": "BOTTLE"})
    assert (taken.status_code, taken.json()["code"]) == (409, "CLASS_NAME_TAKEN")

    renamed = client.patch(f"/api/projects/{pid}/classes/0", json={"name": "tuna 425g"})
    assert renamed.json() == {"index": 0, "name": "tuna_425g", "detectorPrompt": "", "description": "Red tin"}

    assert [c["name"] for c in client.get(f"/api/projects/{pid}/classes").json()] == ["tuna_425g", "bottle"]
    assert client.get(f"/api/projects/{pid}").json()["name"] == "Shelf scans"


def test_rename_to_a_taken_name_is_409_and_leaves_the_class_unchanged(client):
    pid = client.post("/api/projects", json={"name": "P"}).json()["id"]
    client.post(f"/api/projects/{pid}/classes", json={"name": "can"})
    client.post(f"/api/projects/{pid}/classes", json={"name": "jar"})

    r = client.patch(f"/api/projects/{pid}/classes/1", json={"name": "Can"})

    assert (r.status_code, r.json()["code"]) == (409, "CLASS_NAME_TAKEN")
    assert [c["name"] for c in client.get(f"/api/projects/{pid}/classes").json()] == ["can", "jar"]


def _jpg():
    buf = io.BytesIO()
    Image.new("RGB", (100, 50)).save(buf, format="JPEG")
    return buf.getvalue()


def test_import_against_real_postgres_creates_classes_boxes_and_counts(client):
    pid = client.post("/api/projects", json={"name": "Imported"}).json()["id"]
    files = [
        ("files", ("ds/images/a.jpg", _jpg(), "image/jpeg")),
        ("files", ("ds/images/b.jpg", _jpg(), "image/jpeg")),
        ("files", ("ds/labels/a.txt", b"0 0.5 0.5 0.2 0.2\n2 0.3 0.3 0.1 0.1\n", "text/plain")),
        ("files", ("ds/labels/_annot_state.json", json.dumps({"b.jpg": {"status": "error", "note": "boom", "flag": True, "flag_reason": "unsure"}}).encode(), "application/json")),
        ("files", ("ds/data.yaml", b"names: [can]\n", "text/plain")),
    ]
    result = client.post(f"/api/projects/{pid}/import", files=files).json()
    assert (result["added"], result["labelled"], result["boxes"]) == (2, 1, 2)
    assert (result["classesCreated"], result["placeholderClasses"]) == (["can"], ["class_1", "class_2"])

    images = {i["fileName"]: i for i in client.get(f"/api/projects/{pid}/images").json()["items"]}
    assert (images["a.jpg"]["status"], images["a.jpg"]["boxCount"], images["a.jpg"]["note"]) == ("auto", 2, "imported")
    assert (images["b.jpg"]["status"], images["b.jpg"]["flagged"], images["b.jpg"]["flagReason"]) == ("error", True, "unsure")
    assert [c["name"] for c in client.get(f"/api/projects/{pid}/classes").json()] == ["can", "class_1", "class_2"]


def test_editor_save_round_trip_and_conflict_on_real_timestamps(client):
    pid = client.post("/api/projects", json={"name": "Edit"}).json()["id"]
    client.post(f"/api/projects/{pid}/classes", json={"name": "can"})
    image_id = client.post(f"/api/projects/{pid}/images", files=[("files", ("a.jpg", _jpg(), "image/jpeg"))]).json()["added"][0]["id"]

    opened = client.get(f"/api/images/{image_id}/boxes").json()
    box = {"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5}
    first = client.put(f"/api/images/{image_id}/boxes",
                       json={"boxes": [box], "status": "edited", "expectedUpdatedAt": opened["updatedAt"]})
    assert first.status_code == 200, first.json()
    assert first.json()["image"]["boxCount"] == 1

    # A second save with the version from before the first save is refused.
    stale = client.put(f"/api/images/{image_id}/boxes",
                       json={"boxes": [], "status": "reviewed", "expectedUpdatedAt": opened["updatedAt"]})
    assert (stale.status_code, stale.json()["code"]) == (409, "STALE_IMAGE")
