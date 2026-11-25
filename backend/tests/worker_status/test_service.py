"""WorkerStatusService: what the page shows about the worker and engines, and pausing/resuming an engine."""
from datetime import timedelta

import pytest

from annotator.worker_status.service import OFFLINE_AFTER, WorkerStatusService
from tests.fakes import NOW, FakeWorkerStatusRepository

GEMINI_READY = {"ready": True, "note": "", "models": ["gemini-3.5-flash", "gemini-3.5-flash-lite"]}


@pytest.fixture
def repo():
    return FakeWorkerStatusRepository()


def service_at(repo, seconds_later=0):
    return WorkerStatusService(repo, now=lambda: NOW + timedelta(seconds=seconds_later))


def test_a_recent_heartbeat_means_online_with_each_engines_state(repo):
    repo.heartbeat("pc:1", {"gemini": GEMINI_READY})

    status = service_at(repo, 10).status().model_dump(by_alias=True, mode="json")

    assert status["workerOnline"] is True
    assert status["lastSeenAt"] == "2026-11-23T00:00:00Z"
    assert status["engines"]["gemini"] == {"label": "Gemini", "ready": True, "note": "",
                                           "models": ["gemini-3.5-flash", "gemini-3.5-flash-lite"],
                                           "supportsRefine": True}
    assert status["paused"] == []


def test_an_old_heartbeat_means_offline(repo):
    repo.heartbeat("pc:1", {"gemini": GEMINI_READY})
    assert OFFLINE_AFTER == timedelta(seconds=45)
    assert service_at(repo, 46).status().worker_online is False


def test_without_any_worker_engines_are_listed_but_not_ready(repo):
    status = service_at(repo).status()
    assert (status.worker_online, status.last_seen_at) == (False, None)
    assert (status.engines["gemini"].ready, status.engines["gemini"].models) == (False, [])


def test_engines_the_api_does_not_know_are_left_out_and_unreported_ones_are_not_ready(repo):
    repo.heartbeat("pc:1", {"gemini": GEMINI_READY, "robot": {"ready": True, "note": "", "models": []}})
    engines = service_at(repo).status().engines
    assert "robot" not in engines
    assert engines["gemini"].ready is True
    assert engines["claude"].ready is False


def test_pauses_are_listed_with_the_engine_label_and_reason(repo):
    service = service_at(repo)
    service.pause("gemini", "Gemini daily free quota used up")

    paused = service.status().model_dump(by_alias=True, mode="json")["paused"]

    assert paused == [{"engine": "gemini", "label": "Gemini", "reason": "Gemini daily free quota used up",
                       "pausedAt": "2026-11-23T00:00:00Z"}]


def test_resume_lifts_the_pauses(repo):
    service = service_at(repo)
    service.pause("gemini", "quota")
    assert service.resume().resumed == ["gemini"]
    assert service.status().paused == []


def test_heartbeat_and_stopped_are_for_the_worker(repo):
    service = service_at(repo)
    service.heartbeat("pc:1", {"gemini": GEMINI_READY})
    assert repo.latest().worker_id == "pc:1"
    service.stopped("pc:1")
    assert repo.latest() is None
