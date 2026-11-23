"""app.py health report and exports, on a small fixed dataset.

Dataset (classes can=0, bottle=1; images 100x50):
  a.jpg  two identical can boxes (duplicate) + one bottle box
  b.jpg  labelled with no boxes (background)
  c.jpg  one box with class id 5 (not in the list) that is also tiny in width
  d.jpg  no label; status error; flagged
"""
import io
import json
import zipfile

import pytest

import app

CAN = {"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.3, "y2": 0.3}
BOTTLE = {"cls": 1, "x1": 0.5, "y1": 0.5, "x2": 0.9, "y2": 0.9}
ODD = {"cls": 5, "x1": 0.5, "y1": 0.1, "x2": 0.503, "y2": 0.3}


@pytest.fixture
def dataset(project):
    project.write_boxes("a.jpg", [CAN, dict(CAN), BOTTLE])
    project.write_boxes("b.jpg", [])
    project.write_boxes("c.jpg", [ODD])
    project.set_status("d.jpg", "error", "gemini: boom")
    project.set_flag("d.jpg", True, "unsure")
    return project


# ---------- health ----------
def test_health_summary(dataset):
    s = app.health_report(dataset)["summary"]
    assert s == {
        "images": 4, "labeled": 3, "boxes": 4, "avg_boxes_per_image": 1.3,
        "classes": 2, "classes_with_data": 2, "imbalance_ratio": 2.0,
        "status": {"auto": 3, "error": 1},
    }


def test_health_per_class_counts_area_and_warnings(dataset):
    h = app.health_report(dataset, low_count=2)
    assert h["low_count"] == 2
    assert h["classes"] == [
        {"id": 0, "name": "can", "boxes": 2, "images": 1, "avg_area_pct": 4.0, "warn": "", "image_list": ["a.jpg"]},
        {"id": 1, "name": "bottle", "boxes": 1, "images": 1, "avg_area_pct": 16.0, "warn": "low (< 2)", "image_list": ["a.jpg"]},
    ]


def test_health_class_with_no_boxes_says_so(project):
    project.write_boxes("a.jpg", [CAN])
    classes = app.health_report(project)["classes"]
    assert [c["warn"] for c in classes] == ["low (< 100)", "no boxes"]


def test_health_size_buckets_and_heatmap(dataset):
    h = app.health_report(dataset)
    assert h["sizes"] == {"tiny (<0.1%)": 1, "small (0.1-1%)": 0, "medium (1-10%)": 2, "large (>10%)": 1}
    assert len(h["heatmap"]) == 20 and all(len(row) == 20 for row in h["heatmap"])
    assert sum(map(sum, h["heatmap"])) == 4
    assert h["heatmap"][4][4] == 2  # both can boxes are centred at (0.2, 0.2)


def test_health_issues_list_the_right_images(dataset):
    issues = {i["key"]: i for i in app.health_report(dataset)["issues"]}
    assert list(issues) == ["flagged", "unlabeled", "errors", "empty", "duplicates", "tiny", "bad_class", "crowded"]
    assert {k: v["images"] for k, v in issues.items()} == {
        "flagged": ["d.jpg"], "unlabeled": ["d.jpg"], "errors": ["d.jpg"], "empty": ["b.jpg"],
        "duplicates": ["a.jpg"], "tiny": ["c.jpg"], "bad_class": ["c.jpg"], "crowded": [],
    }
    assert issues["duplicates"]["label"] == "Possible duplicate boxes (same class, IoU > 0.85)"
    assert issues["errors"]["count"] == 1


def test_health_crowded_means_more_than_100_boxes(project):
    project.write_boxes("a.jpg", [dict(CAN, x1=0.001 * i, x2=0.001 * i + 0.2) for i in range(101)])
    issues = {i["key"]: i["images"] for i in app.health_report(project)["issues"]}
    assert issues["crowded"] == ["a.jpg"]


# ---------- YOLO export ----------
def _zip_names(buf):
    return sorted(zipfile.ZipFile(buf).namelist())


def test_yolo_zip_layout_and_data_yaml(dataset):
    buf = app.export_yolo_zip(dataset)
    z = zipfile.ZipFile(buf)
    assert sorted(z.namelist()) == [
        "dataset/data.yaml",
        "dataset/images/train/a.jpg", "dataset/images/train/b.jpg", "dataset/images/train/c.jpg",
        "dataset/labels/train/a.txt", "dataset/labels/train/b.txt", "dataset/labels/train/c.txt",
    ]
    assert z.read("dataset/data.yaml").decode() == (
        "path: .\ntrain: images/train\nval: images/val\n\nnames:\n  0: can\n  1: bottle\n")
    assert z.read("dataset/labels/train/b.txt") == b""


def test_yolo_val_split_is_int_of_ratio_and_repeatable_with_seed_0(dataset):
    names1 = _zip_names(app.export_yolo_zip(dataset, val_ratio=0.5))
    names2 = _zip_names(app.export_yolo_zip(dataset, val_ratio=0.5))
    assert names1 == names2
    assert sum(1 for n in names1 if n.startswith("dataset/images/val/")) == 1
    assert sum(1 for n in names1 if n.startswith("dataset/images/train/")) == 2


def test_yolo_only_reviewed_and_skip_flagged(dataset):
    dataset.set_status("a.jpg", "reviewed")
    assert [n for n in _zip_names(app.export_yolo_zip(dataset, only_reviewed=True)) if "/images/" in n] == [
        "dataset/images/train/a.jpg"]
    dataset.set_flag("a.jpg", True)
    assert [n for n in _zip_names(app.export_yolo_zip(dataset, skip_flagged=True)) if "/images/" in n] == [
        "dataset/images/train/b.jpg", "dataset/images/train/c.jpg"]


# ---------- COCO export ----------
def test_coco_categories_images_and_pixel_boxes(dataset):
    coco = app.export_coco(dataset)
    assert coco["categories"] == [{"id": 0, "name": "can"}, {"id": 1, "name": "bottle"}]
    assert coco["images"] == [
        {"id": 1, "file_name": "a.jpg", "width": 100, "height": 50},
        {"id": 2, "file_name": "b.jpg", "width": 100, "height": 50},
        {"id": 3, "file_name": "c.jpg", "width": 100, "height": 50},
    ]
    first = coco["annotations"][0]
    assert first == {"id": 1, "image_id": 1, "category_id": 0, "bbox": [10.0, 5.0, 20.0, 10.0], "area": 200.0, "iscrowd": 0}
    assert [a["category_id"] for a in coco["annotations"]] == [0, 0, 1, 5]  # unknown class ids are kept
    assert json.loads(json.dumps(coco)) == coco


def test_coco_only_reviewed_and_skip_flagged(dataset):
    dataset.set_status("c.jpg", "reviewed")
    assert [i["file_name"] for i in app.export_coco(dataset, only_reviewed=True)["images"]] == ["c.jpg"]
    dataset.set_flag("c.jpg", True)
    assert app.export_coco(dataset, only_reviewed=True, skip_flagged=True)["images"] == []


# ---------- read via the Flask API (a few routes the new API must match) ----------
def test_flask_run_targets_pick_the_same_images_v2_must_pick(dataset, monkeypatch):
    started = {}
    client = app.create_app(dataset).test_client()
    monkeypatch.setattr(app.Worker, "start", lambda self, names, *a: started.setdefault("names", names) or True)
    client.post("/api/run", json={"target": "unlabeled"})
    assert started["names"] == ["d.jpg"]  # "none" or "error": d is unlabeled AND error
    started.clear()
    client.post("/api/run", json={"target": "auto", "mode": "refine"})
    assert started["names"] == ["a.jpg", "b.jpg", "c.jpg"]


def test_flask_save_labels_defaults_status_to_reviewed(dataset):
    client = app.create_app(dataset).test_client()
    client.post("/api/labels/a.jpg", data=json.dumps({"boxes": [CAN]}), content_type="application/json")
    assert dataset.status("a.jpg") == "reviewed"
    assert len(dataset.read_boxes("a.jpg")) == 1
