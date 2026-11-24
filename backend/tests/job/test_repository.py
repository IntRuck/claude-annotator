"""Job queue against real Postgres (V6): enqueue, claim with SKIP LOCKED, finish, cancel, recover."""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from annotator.image.repository import ImageRepository
from annotator.job.repository import JobRepository
from annotator.project.repository import ProjectRepository

pytestmark = pytest.mark.db

OPTIONS = {"model": "gemini-x", "extra": ""}


@pytest.fixture
def pid(db_session):
    return ProjectRepository(db_session).create("P").id


def images(db_session, pid, *names):
    repo = ImageRepository(db_session)
    return [repo.add(pid, file_name=n, stem=n, storage_path=n, thumb_path=n, width=10, height=10).id for n in names]


def enqueue(repo, pid, ids):
    return repo.enqueue(pid, ids, kind="annotate", engine="gemini", options=OPTIONS)


def test_enqueue_queues_one_job_per_image_in_order(db_session, pid):
    repo = JobRepository(db_session)
    a, b = images(db_session, pid, "a", "b")

    queued = enqueue(repo, pid, [a, b])

    jobs = [repo.get(j) for j in queued]
    assert [(j.image_id, j.status, j.kind, j.engine, j.options) for j in jobs] == [
        (a, "queued", "annotate", "gemini", OPTIONS), (b, "queued", "annotate", "gemini", OPTIONS)]


def test_an_image_with_an_open_job_is_skipped_but_a_finished_job_does_not_block(db_session, pid):
    repo = JobRepository(db_session)
    a, b, c = images(db_session, pid, "a", "b", "c")
    first = enqueue(repo, pid, [a, b])
    repo.finish(first[1], "done")

    again = enqueue(repo, pid, [a, b, c])

    assert sorted(repo.get(j).image_id for j in again) == [b, c]


def test_claim_takes_the_oldest_queued_job_and_marks_it_running(db_session, pid):
    repo = JobRepository(db_session)
    a, b = images(db_session, pid, "a", "b")
    enqueue(repo, pid, [a, b])

    job = repo.claim_next()

    assert (job.image_id, job.status) == (a, "running")
    assert job.started_at is not None
    assert repo.claim_next().image_id == b
    assert repo.claim_next() is None


def test_finish_records_the_outcome(db_session, pid):
    repo = JobRepository(db_session)
    [job_id] = enqueue(repo, pid, images(db_session, pid, "a"))
    repo.claim_next()

    job = repo.finish(job_id, "failed", "Gemini HTTP 500")

    assert (job.status, job.error) == ("failed", "Gemini HTTP 500")
    assert job.finished_at is not None


def test_cancel_queued_leaves_the_running_job_and_other_projects_alone(db_session, pid):
    repo = JobRepository(db_session)
    enqueue(repo, pid, images(db_session, pid, "a", "b", "c"))
    other = ProjectRepository(db_session).create("Other").id
    enqueue(repo, other, images(db_session, other, "x"))
    running = repo.claim_next()

    assert repo.cancel_queued(pid) == 2
    assert repo.get(running.id).status == "running"
    assert repo.summary(other)["queued"] == 1


def test_requeue_running_puts_interrupted_jobs_back_in_the_queue(db_session, pid):
    repo = JobRepository(db_session)
    enqueue(repo, pid, images(db_session, pid, "a"))
    job = repo.claim_next()

    assert repo.requeue_running() == 1
    assert repo.get(job.id).status == "queued"


def test_summary_counts_queued_and_lists_running(db_session, pid):
    repo = JobRepository(db_session)
    enqueue(repo, pid, images(db_session, pid, "a", "b", "c"))
    running = repo.claim_next()

    summary = repo.summary(pid)

    assert summary["queued"] == 2
    assert [j.id for j in summary["running"]] == [running.id]


def test_two_workers_claiming_at_once_never_get_the_same_job(pg_engine):
    """FOR UPDATE SKIP LOCKED: a job one worker has locked is skipped by the other."""
    with pg_engine.begin() as c:
        pid = c.execute(text("insert into projects (name) values ('race') returning id")).scalar_one()
    try:
        with Session(pg_engine) as setup:
            enqueue(JobRepository(setup), pid, images(setup, pid, "a", "b"))
            setup.commit()
        with Session(pg_engine) as first, Session(pg_engine) as second:
            one = JobRepository(first).claim_next()       # locked, not committed yet
            two = JobRepository(second).claim_next()
            assert one is not None and two is not None
            assert one.id != two.id
            first.rollback()
            second.rollback()
    finally:
        with pg_engine.begin() as c:
            c.execute(text("delete from projects where id = :p"), {"p": pid})


def test_cancel_queued_can_be_limited_to_one_engine(db_session, pid):
    repo = JobRepository(db_session)
    a, b = images(db_session, pid, "a", "b")
    repo.enqueue(pid, [a], kind="annotate", engine="gemini", options={})
    repo.enqueue(pid, [b], kind="annotate", engine="ollama", options={})

    assert repo.cancel_queued(pid, engine="gemini") == 1
    assert repo.summary(pid)["queued"] == 1


def test_jobs_of_a_paused_engine_wait_until_it_is_resumed(db_session, pid):
    from annotator.worker_status.repository import WorkerStatusRepository

    repo, pauses = JobRepository(db_session), WorkerStatusRepository(db_session)
    a, b = images(db_session, pid, "a", "b")
    repo.enqueue(pid, [a], kind="annotate", engine="gemini", options={})
    repo.enqueue(pid, [b], kind="annotate", engine="ollama", options={})
    pauses.pause("gemini", "quota")

    assert repo.claim_next().image_id == b
    assert repo.claim_next() is None

    pauses.resume()
    assert repo.claim_next().image_id == a


def test_requeue_puts_one_job_back_and_count_queued_counts_per_engine(db_session, pid):
    repo = JobRepository(db_session)
    a, b, c = images(db_session, pid, "a", "b", "c")
    repo.enqueue(pid, [a, b], kind="annotate", engine="gemini", options={})
    repo.enqueue(pid, [c], kind="annotate", engine="ollama", options={})
    job = repo.claim_next()

    repo.requeue(job.id)

    assert repo.get(job.id).status == "queued"
    assert repo.get(job.id).started_at is None
    assert repo.count_queued(pid, engine="gemini") == 2
    assert repo.count_queued(pid) == 3
