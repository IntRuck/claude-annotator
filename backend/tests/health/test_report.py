"""The health report, moved from today's app.health_report (see the old app's tests).

Same small dataset as the old app's test, as v2 rows (classes can=0, bottle=1). Today's c.jpg had a box with class 5;
v2's database refuses a box whose class doesn't exist, so c.jpg's tiny box is a can here and the "class ID not in
class list" issue is gone.
  1 a.jpg  auto: two identical can boxes (duplicate) + one bottle box
  2 b.jpg  auto: no boxes (background)
  3 c.jpg  auto: one can box that is tiny in width
  4 d.jpg  error, no boxes, flagged
"""
from types import SimpleNamespace

from annotator.health.report import build_report

CAN = {"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.3, "y2": 0.3}
BOTTLE = {"cls": 1, "x1": 0.5, "y1": 0.5, "x2": 0.9, "y2": 0.9}
THIN = {"cls": 0, "x1": 0.5, "y1": 0.1, "x2": 0.503, "y2": 0.3}
CLASSES = [(0, "can"), (1, "bottle")]


def image(id, status="auto", flagged=False):
    return SimpleNamespace(id=id, status=status, flagged=flagged)


IMAGES = [image(1), image(2), image(3), image(4, "error", flagged=True)]
BOXES = {1: [CAN, dict(CAN), BOTTLE], 3: [THIN]}


def report(**kw):
    return build_report(CLASSES, IMAGES, BOXES, **kw)


def test_summary():
    assert report()["summary"] == {
        "images": 4, "labeled": 3, "boxes": 4, "avg_boxes_per_image": 1.3,
        "classes": 2, "classes_with_data": 2, "imbalance_ratio": 3.0,
        "status": {"auto": 3, "error": 1},
    }


def test_per_class_counts_area_warnings_and_images():
    h = report(low_count=2)
    assert h["low_count"] == 2
    assert h["classes"] == [
        {"index": 0, "name": "can", "boxes": 3, "images": 2, "avg_area_pct": 2.69, "warn": "", "image_ids": [1, 3]},
        {"index": 1, "name": "bottle", "boxes": 1, "images": 1, "avg_area_pct": 16.0, "warn": "low (< 2)",
         "image_ids": [1]},
    ]


def test_a_class_with_no_boxes_says_so():
    classes = build_report(CLASSES, [image(1)], {1: [CAN]})["classes"]
    assert [c["warn"] for c in classes] == ["low (< 100)", "no boxes"]


def test_size_buckets():
    assert report()["sizes"] == [
        {"key": "tiny", "label": "tiny (<0.1%)", "count": 1},
        {"key": "small", "label": "small (0.1-1%)", "count": 0},
        {"key": "medium", "label": "medium (1-10%)", "count": 2},
        {"key": "large", "label": "large (>10%)", "count": 1},
    ]


def test_heatmap_counts_box_centres_on_a_20_by_20_grid():
    heat = report()["heatmap"]
    assert len(heat) == 20 and all(len(row) == 20 for row in heat)
    assert sum(map(sum, heat)) == 4
    assert heat[4][4] == 2  # both can boxes are centred at (0.2, 0.2)
    assert heat[4][10] == 1 and heat[14][14] == 1


def test_issues_list_the_right_images():
    issues = {i["key"]: i for i in report()["issues"]}
    assert list(issues) == ["flagged", "unlabeled", "errors", "empty", "duplicates", "tiny", "crowded"]
    assert {k: v["image_ids"] for k, v in issues.items()} == {
        "flagged": [4], "unlabeled": [4], "errors": [4], "empty": [2], "duplicates": [1], "tiny": [3], "crowded": [],
    }
    assert issues["duplicates"]["label"] == "Possible duplicate boxes (same class, IoU > 0.85)"
    assert issues["errors"]["label"] == "AI errors"
    assert issues["errors"]["count"] == 1


def test_crowded_means_more_than_100_boxes():
    many = [dict(CAN, x1=0.001 * i, x2=0.001 * i + 0.2) for i in range(101)]
    issues = {i["key"]: i["image_ids"] for i in build_report(CLASSES, [image(1), image(2)],
                                                             {1: many, 2: many[:100]})["issues"]}
    assert issues["crowded"] == [1]


def test_an_image_with_boxes_counts_as_labelled_whatever_its_status():
    # e.g. imported with today's status "none" while its label file had boxes
    h = build_report(CLASSES, [image(1, "unlabeled"), image(2, "unlabeled")], {1: [CAN]})
    assert h["summary"]["labeled"] == 1
    assert {i["key"]: i["image_ids"] for i in h["issues"]}["unlabeled"] == [2]


def test_an_empty_project():
    h = build_report([], [], {})
    assert h["summary"] == {"images": 0, "labeled": 0, "boxes": 0, "avg_boxes_per_image": 0, "classes": 0,
                            "classes_with_data": 0, "imbalance_ratio": 0, "status": {}}
    assert h["classes"] == [] and sum(map(sum, h["heatmap"])) == 0


# ---------- outlines ----------
def test_partly_outlined_images_are_listed():
    outlined = {**CAN, "points": [[0.1, 0.1], [0.3, 0.1], [0.2, 0.3]]}
    plain = {**BOTTLE, "points": None}
    boxes = {1: [outlined, dict(outlined)], 2: [outlined, plain], 3: [plain]}
    issues = {i["key"]: i for i in build_report(CLASSES, [image(1), image(2), image(3)], boxes)["issues"]}
    assert issues["partly_outlined"]["image_ids"] == [2]
    assert issues["partly_outlined"]["label"] == "Partly outlined (some objects have no outline)"
    assert list(issues)[-1] == "partly_outlined"


def test_box_projects_do_not_see_the_outline_issue():
    assert "partly_outlined" not in {i["key"] for i in report()["issues"]}
