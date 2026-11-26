import pytest
from fastapi.testclient import TestClient

from annotator.activity.service import ActivityService
from annotator.classes.schemas import ClassCreate
from annotator.classes.service import ClassService
from annotator.image.service import ImageService
from annotator.job.router import get_job_service
from annotator.job.service import JobService
from annotator.main import create_app
from annotator.project.service import ProjectService
from tests.fakes import (
    FakeActivityRepository,
    FakeClassRepository,
    FakeImageRepository,
    FakeJobRepository,
    FakeProjectRepository,
    FakeStorage,
)


@pytest.fixture
def client():
    app = create_app()
    projects = ProjectService(FakeProjectRepository())
    projects.create_project("Shelf")
    classes = ClassService(FakeClassRepository(), projects)
    classes.add_class(1, ClassCreate(name="can"))
    image_repo = FakeImageRepository()
    for name in ("a.jpg", "b.jpg"):
        image_repo.add(1, file_name=name, stem=name, storage_path=name, thumb_path=name, width=10, height=10)
    images = ImageService(image_repo, FakeStorage(), projects)
    jobs = JobService(FakeJobRepository(), projects, images, classes, ActivityService(FakeActivityRepository(), projects))
    app.dependency_overrides[get_job_service] = lambda: jobs
    return TestClient(app)


def test_post_jobs_queues_and_says_how_many(client):
    r = client.post("/api/projects/1/jobs", json={"target": "unlabeled", "engine": "gemini",
                                                  "options": {"model": "gemini-x", "extra": ""}})
    assert r.status_code == 202
    assert r.json() == {"matched": 2, "queued": 2, "alreadyQueued": 0}


def test_post_jobs_for_one_image(client):
    r = client.post("/api/projects/1/jobs", json={"target": "image", "imageId": 2})
    assert r.json()["queued"] == 1


def test_summary_and_stop(client):
    client.post("/api/projects/1/jobs", json={"target": "unlabeled"})
    assert client.get("/api/projects/1/jobs/summary").json() == {"queued": 2, "running": []}

    r = client.post("/api/projects/1/jobs/stop")

    assert r.json() == {"cancelled": 2}
    assert client.get("/api/projects/1/jobs/summary").json()["queued"] == 0


@pytest.mark.parametrize(("body", "field"), [
    ({"target": "everything"}, "target"),
    ({"target": "unlabeled", "kind": "paint"}, "kind"),
])
def test_a_word_outside_the_list_is_a_validation_error_naming_the_field(client, body, field):
    r = client.post("/api/projects/1/jobs", json=body)
    assert (r.status_code, r.json()["code"]) == (400, "VALIDATION_FAILED")
    assert [e["field"] for e in r.json()["errors"]] == [field]


def test_the_docs_list_the_allowed_kinds_and_targets(client):
    props = client.get("/openapi.json").json()["components"]["schemas"]["JobCreate"]["properties"]
    assert props["kind"]["enum"] == ["annotate", "refine"]
    assert props["target"]["enum"] == ["image", "unlabeled", "errors", "all", "auto"]
