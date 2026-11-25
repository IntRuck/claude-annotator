import io
import zipfile

import pytest

from annotator.common.problem import ApiError
from annotator.storage.storage_service import StorageError


def error_of(fn):
    with pytest.raises(ApiError) as e:
        fn()
    return e.value.status, e.value.code


def zip_of(service, project_id=1, **kw):
    buf = io.BytesIO()
    service.write_yolo(project_id, buf, **kw)
    return zipfile.ZipFile(buf)


def test_flagged_images_are_left_out_by_default_like_today(service):
    s = service.summary(1)
    assert (s.images, s.boxes, s.train, s.val) == (2, 3, 2, 0)


def test_summary_follows_the_options(service):
    assert service.summary(1, skip_flagged=False).images == 3
    s = service.summary(1, only_reviewed=True)
    assert (s.images, s.boxes) == (1, 1)


def test_summary_is_sent_with_camel_case_names(service):
    assert service.summary(1).model_dump(by_alias=True) == {"images": 2, "boxes": 3, "train": 2, "val": 0}


def test_yolo_zip_has_the_originals_from_storage_and_their_labels(service):
    z = zip_of(service)
    assert sorted(n for n in z.namelist() if "/images/" in n) == ["dataset/images/train/a.jpg",
                                                                   "dataset/images/train/b.jpg"]
    assert z.read("dataset/images/train/b.jpg") == b"pixels of b.jpg"
    assert z.read("dataset/labels/train/b.txt").decode() == "1 0.700000 0.700000 0.400000 0.400000\n"
    assert z.read("dataset/data.yaml").decode().endswith("names:\n  0: can\n  1: bottle\n")


def test_yolo_zip_with_flagged_and_approved_only(service):
    assert [n for n in zip_of(service, skip_flagged=False).namelist() if n.endswith(".txt")] == [
        "dataset/labels/train/a.txt", "dataset/labels/train/b.txt", "dataset/labels/train/c.txt"]
    assert [n for n in zip_of(service, only_reviewed=True).namelist() if n.endswith(".txt")] == [
        "dataset/labels/train/b.txt"]


def test_coco_uses_the_projects_classes_and_image_sizes(service):
    result = service.coco(1)
    assert result["categories"] == [{"id": 0, "name": "can"}, {"id": 1, "name": "bottle"}]
    assert result["images"] == [{"id": 1, "file_name": "a.jpg", "width": 100, "height": 50},
                                {"id": 2, "file_name": "b.jpg", "width": 100, "height": 50}]
    assert [a["category_id"] for a in result["annotations"]] == [0, 0, 1]


def test_missing_project_is_404(service):
    assert error_of(lambda: service.summary(42)) == (404, "PROJECT_NOT_FOUND")
    assert error_of(lambda: service.coco(42)) == (404, "PROJECT_NOT_FOUND")
    assert error_of(lambda: zip_of(service, 42)) == (404, "PROJECT_NOT_FOUND")


def test_storage_down_while_zipping_is_a_clear_error(world):
    service, storage = world
    storage.fail_with = StorageError(0, "connection refused")
    assert error_of(lambda: zip_of(service)) == (502, "STORAGE_UNAVAILABLE")
