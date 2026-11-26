from fastapi.testclient import TestClient

from annotator.main import create_app
from annotator.overview.router import get_overview_service


def client(world):
    app = create_app()
    app.dependency_overrides[get_overview_service] = lambda: world.service
    return TestClient(app)


def test_project_summaries_are_camel_case(world):
    r = client(world).get("/api/project-summaries")
    assert r.status_code == 200
    first = r.json()[0]
    assert (first["name"], first["imageCount"], first["toApprove"], first["classCount"]) == ("Shelf", 4, 1, 2)
    assert first["coverImageId"] == 1
    assert "lastChangedAt" in first


def test_delete_project_is_204(world):
    r = client(world).delete("/api/projects/1")
    assert r.status_code == 204
    assert world.projects.get(1) is None


def test_delete_missing_project_is_problem_404(world):
    r = client(world).delete("/api/projects/99")
    assert (r.status_code, r.json()["code"]) == (404, "PROJECT_NOT_FOUND")
