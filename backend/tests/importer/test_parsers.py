"""File readers for importing an existing dataset. The classes.txt, data.yaml and YOLO cases are the same as
today's app (the old app's tests) so the moved code keeps its behaviour."""
import json

import pytest

from annotator.importer.parsers import (
    StateEntry,
    classify,
    parse_annot_state,
    parse_classes_txt,
    parse_data_yaml_names,
    parse_yolo_label,
)


# ---------- classes.txt (today's Project.class_entries) ----------
def test_classes_txt_reads_name_prompt_and_description_and_skips_blank_lines():
    text = "cream_bottle\nspray_bottle | blue spray bottle\nsardine | red tin | Short red tin\n\n"
    assert parse_classes_txt(text) == [
        ("cream_bottle", "", ""),
        ("spray_bottle", "blue spray bottle", ""),
        ("sardine", "red tin", "Short red tin"),
    ]


def test_classes_txt_keeps_a_bar_inside_the_description():
    assert parse_classes_txt("a | b | c | d\n") == [("a", "b", "c | d")]


# ---------- data.yaml (today's read_yaml_names) ----------
@pytest.mark.parametrize("text,expected", [
    ("names: [can, 'bottle', \"jar\"]\n", ["can", "bottle", "jar"]),
    ("path: .\nnames:\n  0: can\n  2: jar\n  1: bottle\nnc: 3\n", ["can", "bottle", "jar"]),
    ("names:\n  - can\n  - bottle\ntrain: x\n", ["can", "bottle"]),
    ("train: images/train\n", []),
])
def test_data_yaml_names_list_mapping_and_dash_forms(text, expected):
    assert parse_data_yaml_names(text) == expected


# ---------- YOLO label files (today's read_boxes) ----------
def test_yolo_label_lines_become_corner_boxes_and_bad_lines_are_counted():
    boxes, bad = parse_yolo_label("1 0.5 0.5 0.2 0.4\nbad line\n0 x 0.1 0.1 0.1\n\n2 0.25 0.75 0.5 0.5 0.91\n")
    assert bad == 2
    assert [b["cls"] for b in boxes] == [1, 2]
    assert boxes[0] == pytest.approx({"cls": 1, "x1": 0.4, "y1": 0.3, "x2": 0.6, "y2": 0.7})
    assert boxes[1] == pytest.approx({"cls": 2, "x1": 0.0, "y1": 0.5, "x2": 0.5, "y2": 1.0})


def test_yolo_class_written_as_float_still_reads_as_an_index():
    boxes, bad = parse_yolo_label("3.0 0.5 0.5 0.2 0.2")
    assert (boxes[0]["cls"], bad) == (3, 0)


def test_negative_class_index_is_a_bad_line():
    assert parse_yolo_label("-1 0.5 0.5 0.2 0.2") == ([], 1)


# ---------- _annot_state.json (today's state file) ----------
def test_annot_state_reads_status_note_and_flag_per_file():
    text = json.dumps({
        "a.jpg": {"status": "reviewed", "note": "", "updated": "2026-11-01T10:00:00", "flag": True,
                  "flag_reason": "wrong class", "flag_note": "left can"},
        "b.jpg": {"status": "auto", "note": "via gemini"},
        "c.jpg": {"status": "none"},
    })
    state = parse_annot_state(text)
    assert state["a.jpg"] == StateEntry("reviewed", "", True, "wrong class", "left can")
    assert state["b.jpg"] == StateEntry("auto", "via gemini", False, "", "")
    assert state["c.jpg"].status == "unlabeled"  # today's "none"


def test_annot_state_ignores_unknown_statuses_and_bad_entries():
    state = parse_annot_state(json.dumps({"a.jpg": {"status": "weird"}, "b.jpg": "nope", "c.jpg": {"flag": True}}))
    assert state["a.jpg"].status is None
    assert "b.jpg" not in state
    assert (state["c.jpg"].status, state["c.jpg"].flagged) == (None, True)


def test_annot_state_that_is_not_json_raises_value_error():
    with pytest.raises(ValueError):
        parse_annot_state("{oops")


# ---------- which file is which ----------
def test_classify_sorts_a_dataset_folder_by_file_name():
    kinds = classify([
        "shelf/images/a.jpg", "shelf/images/B.PNG", "shelf/labels/a.txt", "shelf/labels/_annot_state.json",
        "shelf/classes.txt", "shelf/data.yaml", "shelf/dataset.yml", "shelf/readme.md", "shelf/labels/_claude_tmp/x.jpg",
    ])
    assert kinds == {
        "shelf/images/a.jpg": "image", "shelf/images/B.PNG": "image",
        "shelf/labels/a.txt": "label", "shelf/labels/_annot_state.json": "state",
        "shelf/classes.txt": "classes", "shelf/data.yaml": "yaml", "shelf/dataset.yml": "yaml",
        "shelf/readme.md": "ignored", "shelf/labels/_claude_tmp/x.jpg": "ignored",
    }


# ---------- YOLO segmentation lines (outlines) ----------
def test_yolo_segmentation_lines_become_outlines_with_their_box():
    boxes, bad = parse_yolo_label("1 0.2 0.1 0.6 0.3 0.3 0.7")
    assert bad == 0
    [b] = boxes
    assert b["points"] == [[0.2, 0.1], [0.6, 0.3], [0.3, 0.7]]
    assert (b["cls"], b["x1"], b["y1"], b["x2"], b["y2"]) == pytest.approx((1, 0.2, 0.1, 0.6, 0.7))


def test_a_box_line_with_a_confidence_is_still_a_box():
    boxes, bad = parse_yolo_label("0 0.5 0.5 0.2 0.2 0.9")
    assert bad == 0
    assert "points" not in boxes[0]
    assert boxes[0] == pytest.approx({"cls": 0, "x1": 0.4, "y1": 0.4, "x2": 0.6, "y2": 0.6})


def test_an_odd_count_of_outline_numbers_is_unreadable():
    assert parse_yolo_label("0 0.1 0.1 0.5 0.1 0.3 0.5 0.9") == ([], 1)
