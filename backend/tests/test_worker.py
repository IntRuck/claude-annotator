"""The worker process wiring: units of work, wake-ups, and one real run against Postgres with a fake engine."""
import io
import json
import threading

import pytest
from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from annotator.job.loop import JobLoop
from annotator.worker import make_unit, wakes_worker
from tests.fakes import FakeStorage
from tests.labeling.conftest import FakeEngine


@pytest.mark.parametrize(("payload", "wakes"), [
    ({"type": "jobs", "op": "insert", "projectId": 1}, True),
    ({"type": "jobs", "op": "update", "projectId": 1}, True),
    ({"type": "images", "op": "update", "id": 3, "projectId": 1}, False),
])
def test_only_job_changes_wake_the_worker(payload, wakes):
    assert wakes_worker(json.dumps(payload)) is wakes


def test_a_broken_payload_does_not_wake_it():
    assert wakes_worker("not json") is False


class RecordingSession:
    def __init__(self):
        self.calls = []

    def commit(self):
        self.calls.append("commit")

    def rollback(self):
        self.calls.append("rollback")

    def close(self):
        self.calls.append("close")


def test_a_unit_of_work_commits_when_the_step_succeeds_and_rolls_back_when_it_fails():
    sessions = []

    def factory():
        sessions.append(RecordingSession())
        return sessions[-1]

    unit = make_unit(factory, FakeStorage())
    with unit() as services:
        assert services.jobs and services.labeling
    with pytest.raises(ValueError):
        with unit():
            raise ValueError("boom")

    assert [s.calls for s in sessions] == [["commit", "close"], ["rollback", "close"]]


def jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (100, 50)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.db
def test_one_queued_image_is_labelled_end_to_end_against_real_postgres(pg_engine):
    storage = FakeStorage()
    storage.upload("images", "1/a.jpg", jpeg(), "image/jpeg")
    with pg_engine.begin() as c:
        pid = c.execute(text("insert into projects (name) values ('worker') returning id")).scalar_one()
    try:
        with pg_engine.begin() as c:
            c.execute(text("insert into classes (project_id, class_index, name) values (:p, 0, 'can')"), {"p": pid})
            image_id = c.execute(text(
                "insert into images (project_id, file_name, stem, storage_path, thumb_path, width, height) "
                "values (:p, 'a.jpg', 'a', '1/a.jpg', 't', 100, 50) returning id"), {"p": pid}).scalar_one()
            c.execute(text("insert into jobs (project_id, image_id, kind, engine, options) "
                           "values (:p, :i, 'annotate', 'gemini', '{\"model\": \"gemini-x\"}')"),
                      {"p": pid, "i": image_id})
        engine = FakeEngine([([{"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5}], set())])
        unit = make_unit(sessionmaker(bind=pg_engine, expire_on_commit=False), storage)
        loop = JobLoop(unit, lambda name, options: engine, wake=threading.Event(), stop=threading.Event())

        assert loop.run_once() is True

        with pg_engine.connect() as c:
            image = c.execute(text("select status, note, box_count from images where id = :i"), {"i": image_id}).one()
            job = c.execute(text("select status from jobs where image_id = :i"), {"i": image_id}).scalar_one()
            log = c.execute(text("select message from activity_log where project_id = :p"), {"p": pid}).scalars().all()
        assert tuple(image) == ("auto", "via gemini", 1)
        assert job == "done"
        assert len(log) == 1 and log[0].startswith("a.jpg: 1 box(es) in ")
    finally:
        with pg_engine.begin() as c:
            c.execute(text("delete from projects where id = :p"), {"p": pid})
