"""app.py storage: classes, boxes (YOLO files), status/flags, image prep, data.yaml reading."""
import json

import pytest
from PIL import Image

import app


# ---------- classes ----------
def test_class_entries_read_name_prompt_and_description(tmp_path, project):
    project.classes_file.write_text(
        "cream_bottle\nspray_bottle | blue spray bottle\nsardine | red tin | Short red tin\n\n", encoding="utf-8")
    assert project.class_entries() == [
        ("cream_bottle", "", ""),
        ("spray_bottle", "blue spray bottle", ""),
        ("sardine", "red tin", "Short red tin"),
    ]
    assert project.prompts() == ["cream bottle", "blue spray bottle", "red tin"]
    assert project.descriptions() == ["", "", "Short red tin"]


def test_add_class_cleans_name_appends_at_end_and_ignores_duplicates(project):
    assert project.add_class("  tuna   400g ", "red | can", "line1\nline2") == ["can", "bottle", "tuna_400g"]
    assert project.add_class("can") == ["can", "bottle", "tuna_400g"]
    assert project.class_entries()[2] == ("tuna_400g", "red / can", "line1 line2")


def test_update_class_keeps_the_index_and_refuses_a_taken_name(project):
    project.update_class(0, name="tin can", prompt="metal can")
    assert project.class_entries()[0] == ("tin_can", "metal can", "")
    project.update_class(1, name="tin_can")  # taken: name unchanged
    assert project.classes() == ["tin_can", "bottle"]
    project.update_class(5, name="nope")  # out of range: ignored
    assert project.classes() == ["tin_can", "bottle"]


def test_classes_file_format_written_back(project):
    project.add_class("sardine", "", "Red tin")
    project.add_class("spray", "blue bottle")
    assert project.classes_file.read_text(encoding="utf-8") == (
        "can\nbottle\nsardine |  | Red tin\nspray | blue bottle\n")


# ---------- boxes ----------
def test_write_boxes_clamps_sorts_drops_tiny_and_uses_yolo_6_decimals(project):
    n = project.write_boxes("a.jpg", [
        {"cls": 1, "x1": 0.6, "y1": 0.8, "x2": 0.2, "y2": 0.4},      # reversed corners
        {"cls": 0, "x1": -0.5, "y1": 0.5, "x2": 0.5, "y2": 1.5},     # outside the image
        {"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.1005, "y2": 0.5},   # too thin: dropped
    ])
    assert n == 2
    assert project.label_path("a.jpg").read_text(encoding="utf-8") == (
        "1 0.400000 0.600000 0.400000 0.400000\n"
        "0 0.250000 0.750000 0.500000 0.500000\n")


def test_read_boxes_returns_corners_and_skips_short_lines(project):
    project.label_path("a.jpg").write_text("1 0.5 0.5 0.2 0.4\nbad line\n", encoding="utf-8")
    assert project.read_boxes("a.jpg") == [
        {"cls": 1, "x1": pytest.approx(0.4), "y1": pytest.approx(0.3), "x2": pytest.approx(0.6), "y2": pytest.approx(0.7)}]
    assert project.read_boxes("b.jpg") == []


def test_write_no_boxes_leaves_an_empty_label_file(project):
    assert project.write_boxes("a.jpg", []) == 0
    assert project.label_path("a.jpg").read_text(encoding="utf-8") == ""


# ---------- images ----------
def test_images_lists_only_image_files_directly_in_the_folder_sorted(project, make_image):
    make_image(project.images_dir / "Z.PNG")
    (project.images_dir / "notes.txt").write_text("x")
    make_image(project.images_dir / "sub" / "deep.jpg")
    assert project.images() == ["Z.PNG", "a.jpg", "b.jpg", "c.jpg", "d.jpg"]


def test_image_path_refuses_paths_outside_the_folder(project):
    with pytest.raises(FileNotFoundError):
        project.image_path("../classes.txt")
    with pytest.raises(FileNotFoundError):
        project.image_path("missing.jpg")


# ---------- status + flags ----------
def test_status_is_none_then_auto_when_a_label_exists_then_what_was_set(project):
    assert project.status("a.jpg") == "none"
    project.write_boxes("a.jpg", [])
    assert project.status("a.jpg") == "auto"
    project.set_status("a.jpg", "reviewed")
    assert project.status("a.jpg") == "reviewed"


def test_flag_is_separate_from_status_and_survives_status_changes(project):
    project.set_status("a.jpg", "reviewed", "ok")
    project.set_flag("a.jpg", True, "wrong class", "check the left can")
    project.set_status("a.jpg", "auto", "via gemini")
    entry = project.state["a.jpg"]
    assert (entry["status"], entry["flag"], entry["flag_reason"], entry["flag_note"]) == (
        "auto", True, "wrong class", "check the left can")
    project.set_flag("a.jpg", False, "ignored", "ignored")
    assert (project.state["a.jpg"]["flag_reason"], project.state["a.jpg"]["flag_note"]) == ("", "")
    assert project.flagged("a.jpg") is False


def test_state_is_saved_to_annot_state_json(project):
    project.set_status("b.jpg", "error", "gemini: boom")
    saved = json.loads(project.state_file.read_text(encoding="utf-8"))
    assert saved["b.jpg"]["status"] == "error"
    assert saved["b.jpg"]["note"] == "gemini: boom"


# ---------- image prep ----------
def test_prep_image_downscales_to_1568_and_keeps_small_images(tmp_path, make_image):
    big = make_image(tmp_path / "big.jpg", size=(3136, 1000))
    W, H = app.prep_image(big, tmp_path / "big_out.jpg")
    assert (W, H) == (1568, 500)
    assert Image.open(tmp_path / "big_out.jpg").size == (1568, 500)
    small = make_image(tmp_path / "small.jpg", size=(400, 300))
    assert app.prep_image(small, tmp_path / "small_out.jpg", grid=True,
                          boxes=[{"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5}]) == (400, 300)


# ---------- data.yaml ----------
@pytest.mark.parametrize("text,expected", [
    ("names: [can, 'bottle', \"jar\"]\n", ["can", "bottle", "jar"]),
    ("path: .\nnames:\n  0: can\n  2: jar\n  1: bottle\nnc: 3\n", ["can", "bottle", "jar"]),
    ("names:\n  - can\n  - bottle\ntrain: x\n", ["can", "bottle"]),
    ("train: images/train\n", []),
])
def test_read_yaml_names_supports_list_mapping_and_dash_forms(tmp_path, text, expected):
    f = tmp_path / "data.yaml"
    f.write_text(text, encoding="utf-8")
    assert app.read_yaml_names(f) == expected


def test_read_yaml_names_missing_file_is_empty(tmp_path):
    assert app.read_yaml_names(tmp_path / "nope.yaml") == []
