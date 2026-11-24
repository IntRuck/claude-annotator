"""JobService: what "Label all unlabeled", "Find objects with AI" and Stop put in (or take out of) the queue."""
import pytest

from annotator.activity.service import ActivityService
from annotator.classes.schemas import ClassCreate
from annotator.classes.service import ClassService
from annotator.common.problem import ApiError
from annotator.image.service import ImageService
from annotator.job.schemas import JobCreate
from annotator.job.service import JobService
from annotator.project.service import ProjectService
from tests.fakes import (FakeActivityRepository, FakeClassRepository, FakeImageRepository, FakeJobRepository,
                         FakeProjectRepository, FakeStorage)


class World:
    def __init__(self):
        self.projects = ProjectService(FakeProjectRepository())
        self.projects.create_project("Shelf")
        self.projects.create_project("Other")
        self.classes = ClassService(FakeClassRepository(), self.projects)
        self.classes.add_class(1, ClassCreate(name="can"))
        self.image_repo = FakeImageRepository()
        self.images = ImageService(self.image_repo, FakeStorage(), self.projects)
        self.activity_repo = FakeActivityRepository()
        self.activity = ActivityService(self.activity_repo, self.projects)
        self.jobs_repo = FakeJobRepository()
        self.jobs = JobService(self.jobs_repo, self.projects, self.images, self.classes, self.activity)

    def image(self, name, status="unlabeled", project_id=1):
        row = self.image_repo.add(project_id, file_name=name, stem=name, storage_path=name, thumb_path=name,
                                  width=10, height=10)
        row.status = status
        return row.id


@pytest.fixture
def w():
    return World()


def error_of(fn):
    with pytest.raises(ApiError) as e:
        fn()
    return e.value.status, e.value.code


def queued_images(w):
    return [(j.image_id, j.status) for j in w.jobs_repo.rows.values()]


# ---------- queue ----------
def test_label_all_unlabeled_queues_unlabeled_and_error_images_by_name(w):
    a, _, c = w.image("a.jpg"), w.image("b.jpg", "auto"), w.image("c.jpg", "error")
    w.image("d.jpg", "reviewed")

    result = w.jobs.queue(1, JobCreate(target="unlabeled", options={"model": "gemini-x"}))

    assert (result.matched, result.queued, result.already_queued) == (2, 2, 0)
    assert queued_images(w) == [(a, "queued"), (c, "queued")]
    job = w.jobs_repo.get(1)
    assert (job.kind, job.engine) == ("annotate", "gemini")
    assert job.options == {"model": "gemini-x", "extra": "", "onlyIfStatus": ["unlabeled", "error"]}
    assert w.activity_repo.messages() == ["Queued 2 image(s) for Gemini (gemini-x)"]


def test_one_image_is_queued_whatever_its_status(w):
    w.image("a.jpg")
    b = w.image("b.jpg", "reviewed")

    result = w.jobs.queue(1, JobCreate(target="image", image_id=b))

    assert result.queued == 1
    assert queued_images(w) == [(b, "queued")]
    assert "onlyIfStatus" not in w.jobs_repo.get(1).options


@pytest.mark.parametrize(("target", "expected"), [("errors", ["c.jpg"]), ("all", ["a.jpg", "b.jpg", "c.jpg"])])
def test_other_targets(w, target, expected):
    ids = {w.image("a.jpg"): "a.jpg", w.image("b.jpg", "auto"): "b.jpg", w.image("c.jpg", "error"): "c.jpg"}
    w.jobs.queue(1, JobCreate(target=target))
    assert [ids[i] for i, _ in queued_images(w)] == expected


def test_relabelling_everything_does_not_protect_hand_made_labels(w):
    w.image("a.jpg", "reviewed")
    w.jobs.queue(1, JobCreate(target="all"))
    assert "onlyIfStatus" not in w.jobs_repo.get(1).options


def test_pressing_label_all_twice_does_not_queue_an_image_twice(w):
    w.image("a.jpg")
    w.image("b.jpg")
    w.jobs.queue(1, JobCreate(target="unlabeled"))

    again = w.jobs.queue(1, JobCreate(target="unlabeled"))

    assert (again.matched, again.queued, again.already_queued) == (2, 0, 2)
    assert len(w.jobs_repo.rows) == 2
    assert len(w.activity_repo.messages()) == 1


def test_some_already_waiting_is_mentioned(w):
    a = w.image("a.jpg")
    w.image("b.jpg")
    w.jobs.queue(1, JobCreate(target="image", image_id=a))
    w.jobs.queue(1, JobCreate(target="unlabeled"))
    assert w.activity_repo.messages()[-1] == "Queued 1 image(s) for Gemini (gemini-3.5-flash-lite); 1 already waiting"


def test_nothing_to_label_queues_nothing_and_logs_nothing(w):
    w.image("a.jpg", "reviewed")
    result = w.jobs.queue(1, JobCreate(target="unlabeled"))
    assert (result.matched, result.queued) == (0, 0)
    assert w.activity_repo.messages() == []


def test_without_classes_the_ai_has_nothing_to_look_for(w):
    w.image("x.jpg", project_id=2)
    assert error_of(lambda: w.jobs.queue(2, JobCreate(target="unlabeled"))) == (400, "NO_CLASSES")


@pytest.mark.parametrize(("body", "expected"), [
    (dict(target="everything"), (400, "UNKNOWN_TARGET")),
    (dict(target="unlabeled", engine="robot"), (400, "UNKNOWN_ENGINE")),
    (dict(target="unlabeled", kind="paint"), (400, "UNKNOWN_KIND")),
    (dict(target="image"), (400, "IMAGE_REQUIRED")),
])
def test_bad_requests(w, body, expected):
    assert error_of(lambda: w.jobs.queue(1, JobCreate(**body))) == expected


def test_an_image_of_another_project_is_not_found(w):
    other = w.image("x.jpg", project_id=2)
    assert error_of(lambda: w.jobs.queue(1, JobCreate(target="image", image_id=other))) == (404, "IMAGE_NOT_FOUND")


def test_queueing_in_a_missing_project_is_404(w):
    assert error_of(lambda: w.jobs.queue(42, JobCreate(target="unlabeled"))) == (404, "PROJECT_NOT_FOUND")


# ---------- stop ----------
def test_stop_cancels_waiting_images_and_lets_the_current_one_finish(w):
    for n in "abc":
        w.image(f"{n}.jpg")
    w.jobs.queue(1, JobCreate(target="unlabeled"))
    running = w.jobs.claim_next()

    assert w.jobs.stop(1).cancelled == 2
    assert w.jobs_repo.get(running.id).status == "running"
    assert w.activity_repo.messages()[-1] == ("Stopped: 2 waiting image(s) cancelled. "
                                              "The image being labelled now finishes first.")


def test_stop_with_nothing_waiting_logs_nothing(w):
    assert w.jobs.stop(1).cancelled == 0
    assert w.activity_repo.messages() == []


# ---------- summary and the worker's side ----------
def test_summary_counts_waiting_and_names_the_image_being_labelled(w):
    a = w.image("a.jpg")
    w.image("b.jpg")
    w.jobs.queue(1, JobCreate(target="unlabeled"))
    job = w.jobs.claim_next()

    summary = w.jobs.summary(1).model_dump(by_alias=True, mode="json")

    assert summary == {"queued": 1, "running": [{"id": job.id, "imageId": a, "fileName": "a.jpg", "engine": "gemini",
                                                 "kind": "annotate", "startedAt": "2026-11-23T00:00:00Z"}]}


def test_claim_next_gives_the_worker_a_job_dto_or_none(w):
    a = w.image("a.jpg")
    w.jobs.queue(1, JobCreate(target="unlabeled"))
    job = w.jobs.claim_next()
    assert (job.image_id, job.status, job.project_id) == (a, "running", 1)
    assert w.jobs.claim_next() is None


def test_recover_puts_jobs_of_a_crashed_worker_back_in_the_queue(w):
    w.image("a.jpg")
    w.jobs.queue(1, JobCreate(target="unlabeled"))
    job = w.jobs.claim_next()
    assert w.jobs.recover() == 1
    assert w.jobs_repo.get(job.id).status == "queued"


def test_a_usage_limit_fails_the_job_and_cancels_the_rest_for_that_engine(w):
    for n in "abc":
        w.image(f"{n}.jpg")
    w.jobs.queue(1, JobCreate(target="unlabeled"))
    job = w.jobs.claim_next()

    w.jobs.stop_for_limit(job, "Gemini daily free quota used up")

    assert [j.status for j in w.jobs_repo.rows.values()] == ["failed", "cancelled", "cancelled"]
    assert w.jobs_repo.get(job.id).error == "Gemini daily free quota used up"
    entry = w.activity_repo.rows[-1]
    assert entry.level == "warning"
    assert entry.message == ("Gemini usage limit: Gemini daily free quota used up. "
                             "Stopped; 2 waiting image(s) cancelled. Run it again after the limit resets.")
