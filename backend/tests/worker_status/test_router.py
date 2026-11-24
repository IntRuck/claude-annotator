from fastapi.testclient import TestClient

from annotator.main import create_app
from annotator.worker_status.router import get_worker_status_service
from annotator.worker_status.service import WorkerStatusService
from tests.fakes import NOW, FakeWorkerStatusRepository


def client():
    repo = FakeWorkerStatusRepository()
    repo.heartbeat("pc:1", {"gemini": {"ready": False, "note": "No Gemini API key", "models": []}})
    service = WorkerStatusService(repo, now=lambda: NOW)
    service.pause("gemini", "quota")
    app = create_app()
    app.dependency_overrides[get_worker_status_service] = lambda: service
    return TestClient(app)


def test_get_engines_says_whether_the_worker_is_online_and_what_each_engine_can_do():
    body = client().get("/api/engines").json()
    assert body["workerOnline"] is True
    assert body["engines"]["gemini"]["note"] == "No Gemini API key"
    assert body["paused"][0]["engine"] == "gemini"


def test_resume_lifts_the_pauses():
    c = client()
    assert c.post("/api/worker/resume").json() == {"resumed": ["gemini"]}
    assert c.get("/api/engines").json()["paused"] == []
