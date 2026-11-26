"""JobService: what "Label all unlabeled", "Find objects with AI" and Stop put in (or take out of) the queue."""
from typing import get_args

import pytest

from annotator.activity.service import ActivityService
from annotator.classes.schemas import ClassCreate
from annotator.classes.service import ClassService
from annotator.common.problem import ApiError
from annotator.image.service import ImageService
from annotator.job.schemas import JobCreate, JobKind, JobTarget
from annotator.job.service import TARGETS, JobService
from annotator.project.service import ProjectService
from tests.fakes import (
    FakeActivityRepository,
    FakeClassRepository,
    FakeImageRepository,
    FakeJobRepository,
    FakeProjectRepository,
    FakeStorage,
)


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
    (dict(target="unlabeled", engine="robot"), (400, "UNKNOWN_ENGINE")),
    (dict(target="image"), (400, "IMAGE_REQUIRED")),
])
def test_bad_requests(w, body, expected):
    assert error_of(lambda: w.jobs.queue(1, JobCreate(**body))) == expected


def test_the_kinds_and_targets_in_the_docs_match_what_the_queue_accepts():
    assert get_args(JobKind) == tuple(TARGETS)
    assert set(get_args(JobTarget)) == {target for targets in TARGETS.values() for target in targets}


def test_an_image_of_another_project_is_not_found(w):
    other = w.image("x.jpg", project_id=2)
    assert error_of(lambda: w.jobs.queue(1, JobCreate(target="image", image_id=other))) == (404, "IMAGE_NOT_FOUND")


def test_queueing_in_a_missing_project_is_404(w):
    assert error_of(lambda: w.jobs.queue(42, JobCreate(target="unlabeled"))) == (404, "PROJECT_NOT_FOUND")


# ---------- refine ----------
def test_refine_all_queues_ai_labelled_images_not_yet_approved(w):
    w.image("a.jpg")
    b, c = w.image("b.jpg", "auto"), w.image("c.jpg", "auto")
    w.image("d.jpg", "reviewed")

    result = w.jobs.queue(1, JobCreate(kind="refine", target="auto", options={"model": "gemini-x"}))

    assert result.queued == 2
    assert queued_images(w) == [(b, "queued"), (c, "queued")]
    job = w.jobs_repo.get(1)
    assert job.kind == "refine"
    assert job.options["onlyIfStatus"] == ["auto"]
    assert w.activity_repo.messages() == ["Queued 2 image(s) to refine with Gemini (gemini-x)"]


def test_refine_one_image_whatever_its_status(w):
    a = w.image("a.jpg", "reviewed")
    assert w.jobs.queue(1, JobCreate(kind="refine", target="image", image_id=a)).queued == 1


@pytest.mark.parametrize("target", ["unlabeled", "errors", "all"])
def test_refine_only_works_on_one_image_or_the_ai_labelled_ones(w, target):
    assert error_of(lambda: w.jobs.queue(1, JobCreate(kind="refine", target=target))) == (400, "UNKNOWN_TARGET")


def test_label_all_does_not_take_the_refine_target(w):
    assert error_of(lambda: w.jobs.queue(1, JobCreate(target="auto"))) == (400, "UNKNOWN_TARGET")


@pytest.mark.parametrize("detector", ["grounding_dino", "yolo_world"])
def test_a_detector_cannot_refine_and_says_so(w, detector):
    w.image("a.jpg", "auto")
    assert error_of(lambda: w.jobs.queue(1, JobCreate(kind="refine", target="auto", engine=detector))) == (
        400, "CANT_REFINE")


def test_queueing_for_a_detector_logs_its_model(w):
    w.image("a.jpg")
    w.jobs.queue(1, JobCreate(target="unlabeled", engine="yolo_world", options={"model": "yoloe-11s-seg.pt"}))
    assert w.activity_repo.messages()[-1] == "Queued 1 image(s) for YOLO-World (yoloe-11s-seg.pt)"


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


def test_requeue_puts_a_job_back_and_count_queued_counts_it(w):
    for n in "ab":
        w.image(f"{n}.jpg")
    w.jobs.queue(1, JobCreate(target="unlabeled"))
    job = w.jobs.claim_next()

    w.jobs.requeue(job.id)

    assert w.jobs_repo.get(job.id).status == "queued"
    assert w.jobs.count_queued(1, engine="gemini") == 2
