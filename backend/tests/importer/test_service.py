"""Importing an existing dataset folder: images + YOLO labels + class list + today's state file."""
import io
import json

import pytest
from PIL import Image

from annotator.classes.schemas import ClassCreate
from annotator.classes.service import ClassService
from annotator.common.problem import ApiError
from annotator.image.service import ImageService, UploadedFile
from annotator.importer.service import ImportService
from annotator.label.service import LabelService
from annotator.project.service import ProjectService
from tests.fakes import FakeClassRepository, FakeImageRepository, FakeLabelRepository, FakeProjectRepository, FakeStorage


def jpg():
    buf = io.BytesIO()
    Image.new("RGB", (100, 50)).save(buf, format="JPEG")
    return buf.getvalue()


def f(path, content):
    data = content.encode() if isinstance(content, str) else content
    return UploadedFile(file_name=path, content=data, content_type="")


@pytest.fixture
def world():
    projects = ProjectService(FakeProjectRepository())
    projects.create_project("Shelf")
    images_repo = FakeImageRepository()
    labels_repo = FakeLabelRepository(images_repo)
    classes = ClassService(FakeClassRepository(), projects)
    images = ImageService(images_repo, FakeStorage(), projects)
    service = ImportService(images, classes, LabelService(labels_repo, images, classes))
    return service, classes, images, labels_repo


def image_by_name(images, name):
    return next(i for i in images.list_images(1, "all").items if i.file_name == name)


def test_full_dataset_folder_from_todays_app(world):
    service, classes, images, labels = world
    state = {"a.jpg": {"status": "reviewed", "note": ""},
             "b.jpg": {"status": "auto", "note": "via gemini", "flag": True, "flag_reason": "wrong class", "flag_note": "x"}}
    result = service.import_dataset(1, [
        f("shelf/images/a.jpg", jpg()), f("shelf/images/b.jpg", jpg()), f("shelf/images/c.jpg", jpg()),
        f("shelf/labels/a.txt", "0 0.5 0.5 0.2 0.2\n1 0.25 0.25 0.1 0.1\n"),
        f("shelf/labels/b.txt", ""),
        f("shelf/labels/_annot_state.json", json.dumps(state)),
        f("shelf/classes.txt", "can | metal can | Silver tin\nbottle\n"),
        f("shelf/notes.md", "hello"),
    ])

    assert (result.added, result.labelled, result.boxes, result.states_applied) == (3, 2, 2, 2)
    assert result.classes_created == ["can", "bottle"]
    assert result.ignored_files == ["shelf/notes.md"]
    assert [(c.name, c.detector_prompt, c.description) for c in classes.list_classes(1)] == [
        ("can", "metal can", "Silver tin"), ("bottle", "", "")]

    a, b, c = (image_by_name(images, n) for n in ("a.jpg", "b.jpg", "c.jpg"))
    assert (a.status, a.box_count) == ("reviewed", 2)
    assert (b.status, b.note, b.flagged, b.flag_reason, b.box_count) == ("auto", "via gemini", True, "wrong class", 0)
    assert (c.status, c.box_count) == ("unlabeled", 0)
    assert [x["cls"] for x in labels.boxes[a.id]] == [0, 1]
    assert {x["source"] for x in labels.boxes[a.id]} == {"import"}


def test_labelled_images_without_state_become_auto_with_note_imported(world):
    service, _, images, _ = world
    service.import_dataset(1, [f("a.jpg", jpg()), f("a.txt", "0 0.5 0.5 0.2 0.2"), f("classes.txt", "can")])
    a = image_by_name(images, "a.jpg")
    assert (a.status, a.note) == ("auto", "imported")


def test_data_yaml_is_used_when_there_is_no_classes_txt(world):
    service, classes, _, _ = world
    result = service.import_dataset(1, [f("ds/data.yaml", "names:\n  0: can\n  1: jar\n"), f("ds/a.jpg", jpg())])
    assert result.classes_created == ["can", "jar"]
    assert [c.name for c in classes.list_classes(1)] == ["can", "jar"]


def test_classes_txt_wins_over_data_yaml(world):
    service, classes, _, _ = world
    service.import_dataset(1, [f("data.yaml", "names: [x, y]"), f("classes.txt", "can\njar\n")])
    assert [c.name for c in classes.list_classes(1)] == ["can", "jar"]


def test_a_project_that_already_has_classes_keeps_them(world):
    service, classes, _, _ = world
    classes.add_class(1, ClassCreate(name="mine"))
    result = service.import_dataset(1, [f("classes.txt", "can\njar\n")])
    assert result.kept_existing_classes is True
    assert result.classes_created == []
    assert [c.name for c in classes.list_classes(1)] == ["mine"]


def test_unknown_class_ids_in_labels_get_placeholder_classes(world):
    service, classes, images, labels = world
    result = service.import_dataset(1, [f("a.jpg", jpg()), f("a.txt", "3 0.5 0.5 0.2 0.2\n"), f("classes.txt", "can\n")])
    assert result.placeholder_classes == ["class_1", "class_2", "class_3"]
    assert [c.name for c in classes.list_classes(1)] == ["can", "class_1", "class_2", "class_3"]
    assert labels.boxes[image_by_name(images, "a.jpg").id][0]["cls"] == 3


def test_labels_without_a_matching_image_and_bad_lines_are_reported(world):
    service, _, _, _ = world
    result = service.import_dataset(1, [
        f("a.jpg", jpg()), f("a.txt", "0 0.5 0.5 0.2 0.2\nnot a box\n"), f("ghost.txt", "0 0.5 0.5 0.1 0.1"), f("classes.txt", "can"),
    ])
    assert result.labels_without_image == ["ghost.txt"]
    assert result.bad_label_lines == 1


def test_images_that_cannot_be_added_are_skipped_and_their_labels_unused(world):
    service, _, images, _ = world
    images.upload(1, [f("a.jpg", jpg())])
    result = service.import_dataset(1, [f("a.jpg", jpg()), f("a.txt", "0 0.5 0.5 0.2 0.2"), f("classes.txt", "can")])
    assert result.added == 0
    assert [(s.file_name, s.reason) for s in result.skipped] == [("a.jpg", "already in this project")]
    assert result.labels_without_image == ["a.txt"]


def test_unreadable_state_file_is_a_warning_not_a_failure(world):
    service, _, _, _ = world
    result = service.import_dataset(1, [f("a.jpg", jpg()), f("_annot_state.json", "{oops")])
    assert result.added == 1
    assert result.warnings == ["Couldn't read _annot_state.json, so statuses and flags weren't imported."]


def test_label_files_with_a_byte_order_mark_still_read(world):
    service, _, images, _ = world
    service.import_dataset(1, [f("a.jpg", jpg()), f("a.txt", "﻿0 0.5 0.5 0.2 0.2"), f("classes.txt", "﻿can")])
    assert image_by_name(images, "a.jpg").box_count == 1


def test_import_into_a_missing_project_is_404(world):
    service, _, _, _ = world
    with pytest.raises(ApiError) as e:
        service.import_dataset(9, [f("a.jpg", jpg())])
    assert e.value.code == "PROJECT_NOT_FOUND"
