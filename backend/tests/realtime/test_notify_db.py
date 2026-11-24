"""The V4 triggers against real Postgres: committed changes send NOTIFY payloads the listener understands.

NOTIFY is only delivered on commit, so these tests commit for real and delete their project afterwards.
"""
import json
import queue
import threading

import psycopg
import pytest
from sqlalchemy import text

from annotator.realtime.notify_listener import CHANNEL, NotifyListener

pytestmark = pytest.mark.db


def dsn_of(engine) -> str:
    return engine.url.set(drivername="postgresql").render_as_string(hide_password=False)


@pytest.fixture
def received(pg_engine):
    conn = psycopg.connect(dsn_of(pg_engine), autocommit=True)
    conn.execute(f"LISTEN {CHANNEL}")

    def payloads(wait=0.5):
        return [json.loads(n.payload) for n in conn.notifies(timeout=wait)]

    yield payloads
    conn.close()


@pytest.fixture
def project(pg_engine):
    with pg_engine.begin() as c:
        pid = c.execute(text("insert into projects (name) values ('live') returning id")).scalar_one()
    yield pid
    with pg_engine.begin() as c:
        c.execute(text("delete from projects where id = :p"), {"p": pid})


def add_image(c, pid, name="a.jpg") -> int:
    return c.execute(text(
        "insert into images (project_id, file_name, stem, storage_path, thumb_path, width, height) "
        "values (:p, :n, 'a', 's', 't', 10, 10) returning id"), {"p": pid, "n": name}).scalar_one()


def test_image_insert_update_and_delete_each_send_a_payload(pg_engine, project, received):
    with pg_engine.begin() as c:
        image_id = add_image(c, project)
    with pg_engine.begin() as c:
        c.execute(text("update images set status = 'auto' where id = :i"), {"i": image_id})
    with pg_engine.begin() as c:
        c.execute(text("delete from images where id = :i"), {"i": image_id})

    assert received() == [
        {"type": "images", "op": "insert", "id": image_id, "projectId": project},
        {"type": "images", "op": "update", "id": image_id, "projectId": project},
        {"type": "images", "op": "delete", "id": image_id, "projectId": project},
    ]


def test_saving_many_boxes_sends_one_image_update_not_one_per_box(pg_engine, project, received):
    """The box-count trigger updates the image once per box; Postgres folds identical payloads in one commit."""
    with pg_engine.begin() as c:
        c.execute(text("insert into classes (project_id, class_index, name) values (:p, 0, 'can')"), {"p": project})
        image_id = add_image(c, project)
    received()

    with pg_engine.begin() as c:
        for _ in range(5):
            c.execute(text("insert into boxes (image_id, project_id, class_index, x1, y1, x2, y2, source) "
                           "values (:i, :p, 0, 0.1, 0.1, 0.5, 0.5, 'ai')"), {"i": image_id, "p": project})

    assert received() == [{"type": "images", "op": "update", "id": image_id, "projectId": project}]


def test_class_changes_send_the_class_index_as_id(pg_engine, project, received):
    with pg_engine.begin() as c:
        c.execute(text("insert into classes (project_id, class_index, name) values (:p, 0, 'can')"), {"p": project})
    with pg_engine.begin() as c:
        c.execute(text("update classes set description = 'red tin' where project_id = :p"), {"p": project})

    assert received() == [
        {"type": "classes", "op": "insert", "id": 0, "projectId": project},
        {"type": "classes", "op": "update", "id": 0, "projectId": project},
    ]


def test_rolled_back_changes_send_nothing(pg_engine, project, received):
    with pg_engine.connect() as c:
        with c.begin() as tx:
            add_image(c, project)
            tx.rollback()

    assert received() == []


def test_listener_thread_receives_committed_changes(pg_engine, project):
    got, connected = queue.Queue(), threading.Event()
    listener = NotifyListener(dsn_of(pg_engine), on_payload=got.put, on_connect=connected.set)
    listener.start()
    try:
        assert connected.wait(10)
        with pg_engine.begin() as c:
            image_id = add_image(c, project)
        assert json.loads(got.get(timeout=5)) == {"type": "images", "op": "insert", "id": image_id,
                                                  "projectId": project}
    finally:
        listener.stop()
    assert not listener.is_alive()


def test_queueing_many_jobs_sends_one_jobs_payload_per_project(pg_engine, project, received):
    """Jobs notify per statement, not per row: queueing 500 images is one message, not 500."""
    with pg_engine.begin() as c:
        ids = [add_image(c, project, f"{n}.jpg") for n in range(3)]
    received()

    with pg_engine.begin() as c:
        c.execute(text("insert into jobs (project_id, image_id, kind, engine) "
                       "select :p, i, 'annotate', 'gemini' from unnest(cast(:ids as bigint[])) as i"),
                  {"p": project, "ids": ids})
    with pg_engine.begin() as c:
        c.execute(text("update jobs set status = 'cancelled' where project_id = :p"), {"p": project})

    assert received() == [
        {"type": "jobs", "op": "insert", "projectId": project},
        {"type": "jobs", "op": "update", "projectId": project},
    ]


def test_activity_entries_send_a_payload_each(pg_engine, project, received):
    with pg_engine.begin() as c:
        entry_id = c.execute(text("insert into activity_log (project_id, message) values (:p, 'hello') returning id"),
                             {"p": project}).scalar_one()

    assert received() == [{"type": "activity", "op": "insert", "id": entry_id, "projectId": project}]


def test_worker_heartbeats_and_engine_pauses_send_a_worker_payload(pg_engine, received):
    with pg_engine.begin() as c:
        c.execute(text("insert into worker_status (worker_id) values ('pc:9')"))
        c.execute(text("insert into engine_pauses (engine, reason) values ('gemini', 'quota')"))
    try:
        payloads = received()
        assert [(p["type"], p["op"], p["projectId"]) for p in payloads] == [
            ("worker", "insert", None), ("worker", "insert", None)]
    finally:
        with pg_engine.begin() as c:
            c.execute(text("delete from worker_status where worker_id = 'pc:9'"))
            c.execute(text("delete from engine_pauses where engine = 'gemini'"))
