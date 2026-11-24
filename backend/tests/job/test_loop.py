"""JobLoop: what the worker process does over and over (claim -> load -> engine -> save), and its error paths."""
import threading
import time
from contextlib import contextmanager
from types import SimpleNamespace

from annotator.engine.base import LimitReached
from annotator.job.loop import JobLoop
from tests.labeling.conftest import FakeEngine, World

CAN = {"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5}


def loop_for(w: World, **kw) -> JobLoop:
    @contextmanager
    def unit():
        yield SimpleNamespace(jobs=w.jobs, labeling=w.labeling)

    return JobLoop(unit, w.make_engine, wake=kw.pop("wake", threading.Event()), stop=kw.pop("stop", threading.Event()),
                   **kw)


def test_nothing_queued_means_nothing_to_do():
    assert loop_for(World()).run_once() is False


def test_a_queued_image_gets_its_ai_boxes():
    w = World()
    image_id = w.upload("a.jpg")
    w.queue()
    w.engine = FakeEngine([([CAN], set())])

    assert loop_for(w).run_once() is True

    assert w.status(image_id) == "auto"
    assert len(w.label_repo.list_for_image(image_id)) == 1
    assert w.job_repo.get(1).status == "done"


def test_an_engine_error_marks_that_image_and_the_next_one_still_runs():
    w = World()
    a, b = w.upload("a.jpg"), w.upload("b.jpg")
    w.queue()
    w.engine = FakeEngine([RuntimeError("bad reply"), ([CAN], set())])
    loop = loop_for(w)

    loop.run_once()
    loop.run_once()

    assert (w.status(a), w.status(b)) == ("error", "auto")


def test_a_usage_limit_stops_the_rest_without_touching_the_image():
    w = World()
    a, _ = w.upload("a.jpg"), w.upload("b.jpg")
    w.queue()
    w.engine = FakeEngine([LimitReached("quota")])
    loop = loop_for(w)

    loop.run_once()

    assert w.status(a) == "unlabeled"
    assert loop.run_once() is False


def test_an_image_labelled_by_hand_meanwhile_never_reaches_the_engine():
    w = World()
    a = w.upload("a.jpg")
    w.queue()
    w.image_repo.get(a).status = "reviewed"
    w.engine = FakeEngine([])

    assert loop_for(w).run_once() is True
    assert w.engine.calls == []


def test_run_forever_recovers_interrupted_jobs_works_through_the_queue_and_stops_when_asked():
    w = World()
    a, b = w.upload("a.jpg"), w.upload("b.jpg")
    w.queue()
    w.jobs.claim_next()                  # "running" when the previous worker died
    w.engine = FakeEngine([([CAN], set()), ([CAN], set())])
    stop = threading.Event()
    loop = loop_for(w, stop=stop, idle_seconds=0.01)

    thread = threading.Thread(target=loop.run_forever)
    thread.start()
    deadline = time.monotonic() + 5
    while (w.status(a), w.status(b)) != ("auto", "auto") and time.monotonic() < deadline:
        time.sleep(0.01)
    stop.set()
    thread.join(5)

    assert (w.status(a), w.status(b)) == ("auto", "auto")
    assert not thread.is_alive()


def test_a_wake_up_starts_new_work_without_waiting_for_the_idle_timeout():
    w = World()
    wake, stop = threading.Event(), threading.Event()
    loop = loop_for(w, wake=wake, stop=stop, idle_seconds=30)
    thread = threading.Thread(target=loop.run_forever)
    thread.start()
    try:
        time.sleep(0.05)                 # idle, waiting
        image_id = w.upload("a.jpg")
        w.queue()
        w.engine = FakeEngine([([CAN], set())])
        wake.set()                       # what the NOTIFY on the jobs table does
        deadline = time.monotonic() + 5
        while w.status(image_id) != "auto" and time.monotonic() < deadline:
            time.sleep(0.01)
        assert w.status(image_id) == "auto"
    finally:
        stop.set()
        wake.set()
        thread.join(5)
