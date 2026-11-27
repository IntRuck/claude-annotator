from datetime import UTC, datetime, timedelta, timezone

import pytest

from annotator.classes.schemas import ClassCreate
from annotator.classes.service import ClassService
from annotator.common.problem import ApiError
from annotator.image.service import ImageService
from annotator.label.schemas import BoxIn, SaveBoxes
from annotator.label.service import LabelService
from annotator.project.service import ProjectService
from tests.fakes import (
    NOW,
    FakeClassRepository,
    FakeImageRepository,
    FakeLabelRepository,
    FakeProjectRepository,
    FakeStorage,
)


@pytest.fixture
def world():
    projects = ProjectService(FakeProjectRepository())
    projects.create_project("Shelf")
    classes = ClassService(FakeClassRepository(), projects)
    for name in ("can", "bottle"):
        classes.add_class(1, ClassCreate(name=name))
    images_repo = FakeImageRepository()
    images_repo.add(1, file_name="a.jpg", stem="a", storage_path="p", thumb_path="t", width=100, height=50)
    labels_repo = FakeLabelRepository(images_repo)
    service = LabelService(labels_repo, ImageService(images_repo, FakeStorage(), projects), classes)
    return service, labels_repo, images_repo


def box(cls, x1=0.1, y1=0.1, x2=0.5, y2=0.5, source="human", conf=None):
    return BoxIn(cls=cls, x1=x1, y1=y1, x2=x2, y2=y2, source=source, conf=conf)


def error_of(fn):
    with pytest.raises(ApiError) as e:
        fn()
    return e.value.status, e.value.code


# ---------- replace (used by import) ----------
def test_replace_boxes_applies_the_save_rules_and_returns_how_many_were_kept(world):
    service, labels, images = world
    kept = service.replace_boxes(1, 1, [
        {"cls": 0, "x1": 0.5, "y1": 0.5, "x2": 0.1, "y2": 0.1},
        {"cls": 1, "x1": 0.2, "y1": 0.2, "x2": 0.2005, "y2": 0.9},
    ], source="import")
    assert kept == 1
    assert labels.boxes[1] == [pytest.approx({"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5, "source": "import"})]
    assert images.get(1).box_count == 1


# ---------- read ----------
def test_get_boxes_returns_the_boxes_with_the_image_version(world):
    service, _, _ = world
    service.replace_boxes(1, 1, [{"cls": 1, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5, "conf": 0.7}], source="ai")
    out = service.get_boxes(1)
    assert out.updated_at == NOW
    assert [(b.cls, b.source, b.conf) for b in out.boxes] == [(1, "ai", 0.7)]


def test_get_boxes_of_a_missing_image_is_404(world):
    service, _, _ = world
    assert error_of(lambda: service.get_boxes(9)) == (404, "IMAGE_NOT_FOUND")


# ---------- save from the editor ----------
def test_save_replaces_boxes_sets_status_and_keeps_each_box_source(world):
    service, labels, images = world
    out = service.save(1, SaveBoxes(boxes=[box(0, source="ai", conf=0.9), box(1, 0.6, 0.6, 0.9, 0.9)],
                                    status="edited", expected_updated_at=NOW))
    assert (out.image.status, out.image.box_count) == ("edited", 2)
    assert [(b["cls"], b["source"]) for b in labels.boxes[1]] == [(0, "ai"), (1, "human")]
    assert [b.cls for b in out.boxes] == [0, 1]


def test_approve_saves_as_reviewed_and_applies_the_save_rules(world):
    service, labels, _ = world
    out = service.save(1, SaveBoxes(boxes=[box(0, 0.5, 0.5, 0.1, 0.1), box(0, 0.2, 0.2, 0.2005, 0.3)],
                                    status="reviewed", expected_updated_at=NOW))
    assert out.image.status == "reviewed"
    assert len(labels.boxes[1]) == 1


def test_saving_with_an_old_version_is_409_and_changes_nothing(world):
    service, labels, images = world
    old = NOW - timedelta(seconds=5)
    assert error_of(lambda: service.save(1, SaveBoxes(boxes=[box(0)], status="edited", expected_updated_at=old))) == (409, "STALE_IMAGE")
    assert 1 not in labels.boxes
    assert images.get(1).status == "unlabeled"


def test_a_box_with_a_class_the_project_does_not_have_is_400(world):
    service, _, _ = world
    assert error_of(lambda: service.save(1, SaveBoxes(boxes=[box(5)], status="edited", expected_updated_at=NOW))) == (400, "UNKNOWN_CLASS")


def test_unknown_box_source_is_400(world):
    service, _, _ = world
    assert error_of(lambda: service.save(1, SaveBoxes(boxes=[box(0, source="robot")], status="edited",
                                                      expected_updated_at=NOW))) == (400, "BAD_BOX_SOURCE")


def test_same_moment_in_another_timezone_is_not_stale(world):
    service, _, _ = world
    same = NOW.astimezone(timezone(timedelta(hours=8)))
    assert service.save(1, SaveBoxes(boxes=[], status="edited", expected_updated_at=same)).image.status == "edited"


def test_saving_a_missing_image_is_404(world):
    service, _, _ = world
    assert error_of(lambda: service.save(9, SaveBoxes(boxes=[], status="edited",
                                                      expected_updated_at=datetime.now(UTC)))) == (404, "IMAGE_NOT_FOUND")


# ---------- whole project (health report) ----------
def test_boxes_by_image_groups_the_projects_boxes(world):
    service, labels, images = world
    images.add(1, file_name="b.jpg", stem="b", storage_path="p", thumb_path="t", width=100, height=50)
    images.add(1, file_name="c.jpg", stem="c", storage_path="p", thumb_path="t", width=100, height=50)
    images.add(2, file_name="d.jpg", stem="d", storage_path="p", thumb_path="t", width=100, height=50)
    service.replace_boxes(1, 1, [{"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5}], source="ai")
    service.replace_boxes(1, 2, [{"cls": 1, "x1": 0.2, "y1": 0.2, "x2": 0.4, "y2": 0.4, "conf": 0.9},
                                 {"cls": 0, "x1": 0.5, "y1": 0.5, "x2": 0.6, "y2": 0.6}], source="ai")
    service.replace_boxes(2, 4, [{"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5}], source="ai")
    grouped = service.boxes_by_image(1)
    assert list(grouped) == [1, 2]  # images without boxes (c.jpg) and other projects are left out
    assert [b["cls"] for b in grouped[2]] == [1, 0]
    assert grouped[2][0] == pytest.approx({"cls": 1, "x1": 0.2, "y1": 0.2, "x2": 0.4, "y2": 0.4, "source": "ai", "conf": 0.9, "points": None})


# ---------- outlines ----------
TRIANGLE = [(0.2, 0.1), (0.6, 0.3), (0.3, 0.7)]


def test_save_keeps_an_outline_and_works_out_its_box(world):
    service, _, _ = world
    out = service.save(1, SaveBoxes(boxes=[BoxIn(cls=0, x1=0, y1=0, x2=1, y2=1, points=TRIANGLE)],
                                    status="edited", expected_updated_at=NOW))
    [b] = out.boxes
    assert b.points == TRIANGLE
    assert (b.x1, b.y1, b.x2, b.y2) == pytest.approx((0.2, 0.1, 0.6, 0.7))


def test_has_outlines_and_image_ids_with_outlines(world):
    service, _, images = world
    images.add(1, file_name="b.jpg", stem="b", storage_path="p", thumb_path="t", width=100, height=50)
    service.replace_boxes(1, 1, [{"cls": 0, "x1": 0, "y1": 0, "x2": 1, "y2": 1, "points": TRIANGLE},
                                 {"cls": 1, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5}], source="human")
    service.replace_boxes(1, 2, [{"cls": 1, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5}], source="ai")
    assert (service.has_outlines(1), service.has_outlines(2)) == (True, False)
    assert service.image_ids_with_outlines(1) == {1}
