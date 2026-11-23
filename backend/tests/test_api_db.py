"""Whole stack against real Postgres: router -> service -> repository -> Flyway schema -> JSON."""
import pytest
from fastapi.testclient import TestClient

from annotator.db.session import get_session
from annotator.main import create_app

pytestmark = pytest.mark.db


@pytest.fixture
def client(db_session):
    app = create_app()

    def session_in_test_transaction():
        yield db_session
        db_session.flush()

    app.dependency_overrides[get_session] = session_in_test_transaction
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
