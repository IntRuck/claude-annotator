import pytest

from annotator.common.problem import ApiError


def error_of(fn):
    with pytest.raises(ApiError) as e:
        fn()
    return e.value.status, e.value.code


def test_report_reads_the_projects_classes_images_and_boxes(service):
    h = service.report(1, low_count=5)
    assert h.summary.images == 2 and h.summary.labeled == 1 and h.summary.boxes == 2
    assert h.summary.status == {"auto": 1, "unlabeled": 1}
    assert [(c.name, c.boxes, c.image_ids, c.warn) for c in h.classes] == [
        ("can", 2, [2], "low (< 5)"), ("bottle", 0, [], "no boxes")]
    issues = {i.key: i.image_ids for i in h.issues}
    assert issues["unlabeled"] == [1]


def test_report_is_sent_with_camel_case_names(service):
    body = service.report(1).model_dump(by_alias=True, mode="json")
    assert set(body) == {"summary", "classes", "sizes", "heatmap", "issues", "lowCount"}
    assert body["lowCount"] == 100
    assert {"avgBoxesPerImage", "classesWithData", "imbalanceRatio"} <= set(body["summary"])
    assert set(body["classes"][0]) == {"index", "name", "boxes", "images", "avgAreaPct", "warn", "imageIds"}
    assert set(body["issues"][0]) == {"key", "label", "count", "imageIds"}


def test_report_of_a_missing_project_is_404(service):
    assert error_of(lambda: service.report(42)) == (404, "PROJECT_NOT_FOUND")


@pytest.mark.parametrize("low", [0, -3, 100_001])
def test_warn_below_must_be_between_1_and_100000(service, low):
    assert error_of(lambda: service.report(1, low_count=low)) == (400, "BAD_LOW_COUNT")
