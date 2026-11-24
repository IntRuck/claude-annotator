"""Worker heartbeats and engine pauses against real Postgres (V7)."""
import pytest

from annotator.worker_status.repository import WorkerStatusRepository

pytestmark = pytest.mark.db

READY = {"gemini": {"ready": True, "note": "", "models": ["gemini-x"]}}


def test_a_heartbeat_adds_the_worker_then_refreshes_it(db_session):
    repo = WorkerStatusRepository(db_session)
    repo.heartbeat("pc:1", {"gemini": {"ready": False, "note": "No key", "models": []}})
    first = repo.latest().last_seen_at

    repo.heartbeat("pc:1", READY)

    latest = repo.latest()
    assert (latest.worker_id, latest.engines) == ("pc:1", READY)
    assert latest.last_seen_at >= first


def test_latest_is_the_worker_seen_most_recently_and_remove_forgets_one(db_session):
    repo = WorkerStatusRepository(db_session)
    repo.heartbeat("old:1", {})
    repo.heartbeat("new:2", READY)
    assert repo.latest().worker_id == "new:2"

    repo.remove("new:2")

    assert repo.latest().worker_id == "old:1"


def test_pausing_an_engine_twice_keeps_one_pause_with_the_latest_reason(db_session):
    repo = WorkerStatusRepository(db_session)
    repo.pause("gemini", "daily quota")
    repo.pause("gemini", "rate limit")

    assert [(p.engine, p.reason) for p in repo.pauses()] == [("gemini", "rate limit")]


def test_resume_lifts_every_pause_and_says_which(db_session):
    repo = WorkerStatusRepository(db_session)
    repo.pause("gemini", "quota")
    repo.pause("claude", "5-hour limit")

    assert sorted(repo.resume()) == ["claude", "gemini"]
    assert repo.pauses() == []
