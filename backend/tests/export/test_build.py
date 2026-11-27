"""YOLO zip and COCO JSON, moved from today's app.export_yolo_zip / export_coco
(see the old app's tests).

Same small dataset as the old app's test, as v2 rows (classes can=0, bottle=1, images 100x50). Today's c.jpg had a box
with class 5; v2's database refuses that, so c.jpg's box is a can here.
  1 a.jpg  auto: two identical can boxes + one bottle box
  2 b.jpg  auto: no boxes (background)
  3 c.jpg  auto: one thin can box
  4 d.jpg  error, no boxes, flagged
"""
import io
import json
import zipfile
from types import SimpleNamespace

from annotator.export import coco, yolo
from annotator.export.pick import Picked, fully_outlined, pick

CAN = {"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.3, "y2": 0.3}
BOTTLE = {"cls": 1, "x1": 0.5, "y1": 0.5, "x2": 0.9, "y2": 0.9}
THIN = {"cls": 0, "x1": 0.5, "y1": 0.1, "x2": 0.503, "y2": 0.3}
CLASSES = [(0, "can"), (1, "bottle")]


def image(id, name, status="auto", flagged=False):
    return SimpleNamespace(id=id, file_name=name, width=100, height=50, status=status, flagged=flagged)


def dataset(**changes):
    rows = {1: image(1, "a.jpg"), 2: image(2, "b.jpg"), 3: image(3, "c.jpg"), 4: image(4, "d.jpg", "error", True)}
    for image_id, fields in changes.items():
        vars(rows[int(image_id.lstrip("i"))]).update(fields)
    return list(rows.values()), {1: [CAN, dict(CAN), BOTTLE], 3: [THIN]}


def read_image(img):
    return f"pixels of {img.file_name}".encode()


def yolo_zip(picked, **kw):
    buf = io.BytesIO()
    yolo.write_zip(buf, CLASSES, picked, read_image, **kw)
    return zipfile.ZipFile(buf)


def names_in(z, folder="images"):
    return sorted(n for n in z.namelist() if f"/{folder}/" in n)


# ---------- picking ----------
def test_pick_takes_labelled_images_in_list_order_numbered_by_position():
    picked = pick(*dataset())
    assert [(p.number, p.image.file_name, len(p.boxes)) for p in picked] == [(1, "a.jpg", 3), (2, "b.jpg", 0),
                                                                            (3, "c.jpg", 1)]


def test_pick_approved_only_and_leave_out_flagged():
    images, boxes = dataset(i1={"status": "reviewed"}, i3={"status": "reviewed", "flagged": True})
    assert [p.image.file_name for p in pick(images, boxes, only_reviewed=True)] == ["a.jpg", "c.jpg"]
    assert [p.image.file_name for p in pick(images, boxes, only_reviewed=True, skip_flagged=True)] == ["a.jpg"]


# ---------- YOLO ----------
def test_yolo_zip_layout_and_data_yaml():
    z = yolo_zip(pick(*dataset()))
    assert sorted(z.namelist()) == [
        "dataset/data.yaml",
        "dataset/images/train/a.jpg", "dataset/images/train/b.jpg", "dataset/images/train/c.jpg",
        "dataset/labels/train/a.txt", "dataset/labels/train/b.txt", "dataset/labels/train/c.txt",
    ]
    assert z.read("dataset/data.yaml").decode() == (
        "path: .\ntrain: images/train\nval: images/val\n\nnames:\n  0: can\n  1: bottle\n")
    assert z.read("dataset/images/train/a.jpg") == b"pixels of a.jpg"


def test_yolo_label_files_are_class_and_centre_size_with_6_decimals():
    z = yolo_zip(pick(*dataset()))
    assert z.read("dataset/labels/train/a.txt").decode() == (
        "0 0.200000 0.200000 0.200000 0.200000\n"
        "0 0.200000 0.200000 0.200000 0.200000\n"
        "1 0.700000 0.700000 0.400000 0.400000\n")
    assert z.read("dataset/labels/train/b.txt") == b""  # background image: empty label file


def test_yolo_val_split_is_int_of_ratio_and_repeatable_with_seed_0():
    first = names_in(yolo_zip(pick(*dataset()), val_ratio=0.5))
    assert first == names_in(yolo_zip(pick(*dataset()), val_ratio=0.5))
    assert sum(n.startswith("dataset/images/val/") for n in first) == 1
    assert sum(n.startswith("dataset/images/train/") for n in first) == 2


def test_yolo_split_matches_todays_shuffle():
    # today: random.Random(0).shuffle(names); the first int(n * ratio) go to val
    import random
    names = [f"{i:02d}.jpg" for i in range(20)]
    random.Random(0).shuffle(names)
    images = [image(i + 1, f"{i:02d}.jpg") for i in range(20)]
    picked = pick(images, {})
    assert {img.file_name for img in images if yolo.split(picked)[img.id] == "val"} == set(names[:2])


def test_yolo_names_with_yaml_special_characters_are_quoted():
    assert yolo.data_yaml([(0, "can"), (1, "Coke: 330ml"), (2, "#1 pick")]).endswith(
        '  0: can\n  1: "Coke: 330ml"\n  2: "#1 pick"\n')


# ---------- COCO ----------
def test_coco_categories_images_and_pixel_boxes():
    result = coco.build(CLASSES, pick(*dataset()))
    assert result["categories"] == [{"id": 0, "name": "can"}, {"id": 1, "name": "bottle"}]
    assert result["images"] == [
        {"id": 1, "file_name": "a.jpg", "width": 100, "height": 50},
        {"id": 2, "file_name": "b.jpg", "width": 100, "height": 50},
        {"id": 3, "file_name": "c.jpg", "width": 100, "height": 50},
    ]
    assert result["annotations"][0] == {"id": 1, "image_id": 1, "category_id": 0, "bbox": [10.0, 5.0, 20.0, 10.0],
                                        "area": 200.0, "iscrowd": 0}
    assert [a["category_id"] for a in result["annotations"]] == [0, 0, 1, 0]
    assert [a["image_id"] for a in result["annotations"]] == [1, 1, 1, 3]
    assert json.loads(json.dumps(result)) == result


def test_coco_image_ids_are_positions_in_the_whole_list_like_today():
    images, boxes = dataset(i1={"status": "unlabeled"})
    boxes.pop(1)
    assert [i["id"] for i in coco.build(CLASSES, pick(images, boxes))["images"]] == [2, 3]


# ---------- outlines ----------
TRI = [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5]]
OUTLINED = {"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5, "points": TRI}


def test_yolo_outline_lines_are_class_then_dots_with_6_decimals():
    assert yolo.label_text([OUTLINED, {**OUTLINED, "cls": 1}], shape="outlines") == (
        "0 0.100000 0.100000 0.500000 0.100000 0.500000 0.500000\n"
        "1 0.100000 0.100000 0.500000 0.100000 0.500000 0.500000\n")
    assert yolo.label_text([], shape="outlines") == ""


def test_coco_outlines_add_segmentation_in_pixels_and_the_outline_area():
    [a] = coco.build(CLASSES, [Picked(1, image(1, "a.jpg"), [OUTLINED])], shape="outlines")["annotations"]
    assert a["segmentation"] == [[10.0, 5.0, 50.0, 5.0, 50.0, 25.0]]
    assert a["area"] == 400.0
    assert a["bbox"] == [10.0, 5.0, 40.0, 20.0]


def test_fully_outlined_keeps_empty_images_and_counts_the_rest():
    picked = [Picked(1, image(1, "a.jpg"), [OUTLINED]), Picked(2, image(2, "b.jpg"), []),
              Picked(3, image(3, "c.jpg"), [OUTLINED, CAN])]
    kept, left_out = fully_outlined(picked)
    assert ([p.image.file_name for p in kept], left_out) == (["a.jpg", "b.jpg"], 1)
