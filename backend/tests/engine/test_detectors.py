"""Grounding DINO and YOLO-World, moved from backends.py. The real models need torch (not installed for unit tests),
so fakes stand in for the model call; everything around it is the real code: the prompt text, pixel -> 0-1 boxes,
class matching, duplicate removal and keeping only one model loaded."""
import io
from types import SimpleNamespace

from PIL import Image

from annotator.engine.detectors.common import ModelCache, installed, match_class
from annotator.engine.detectors.grounding_dino import DEFAULT_MODEL as DINO_MODEL
from annotator.engine.detectors.grounding_dino import GroundingDinoEngine
from annotator.engine.detectors.yolo_world import DEFAULT_MODEL as YOLO_MODEL
from annotator.engine.detectors.yolo_world import YoloWorldEngine

CLASSES = ["tuna_can", "jar"]
PROMPTS = ["Red Tin Can", "glass jar"]


def jpeg(size=(200, 100)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size).save(buf, format="JPEG")
    return buf.getvalue()


# ---------- shared ----------
def test_match_class_exact_then_longest_substring_overlap_else_none():
    prompts = ["red tin can", "can", "spray bottle"]
    assert match_class("Can", prompts) == 1
    assert match_class("red tin can lid", prompts) == 0
    assert match_class("banana", prompts) is None


def test_only_one_model_stays_loaded_and_the_old_one_is_freed():
    loads, freed = [], []
    cache = ModelCache(free=lambda: freed.append(1))

    assert cache.get("a", lambda: loads.append("a") or "A") == "A"
    assert cache.get("a", lambda: loads.append("a") or "A") == "A"
    assert freed == []
    assert cache.get("b", lambda: loads.append("b") or "B") == "B"
    assert freed == [1]
    cache.get("a", lambda: loads.append("a") or "A")

    assert loads == ["a", "b", "a"]


def test_installed_checks_every_module_without_importing_it():
    assert installed("json") is True
    assert installed("json", "no_such_module_for_sure") is False


# ---------- Grounding DINO ----------
class FakeDino(GroundingDinoEngine):
    """The real engine with the model call replaced: answers `result` in pixels and records what it was asked."""

    def __init__(self, result, cache=None, **kw):
        super().__init__(cache=cache or ModelCache(free=lambda: None), **kw)
        self.result, self.asked, self.loads = result, [], 0

    def _load(self):
        self.loads += 1
        return "dino"

    def _detect(self, loaded, image, text):
        self.asked.append({"loaded": loaded, "size": image.size, "text": text})
        return self.result


def dino_result(*found):
    """found: (box in pixels, score, label) tuples."""
    return {"boxes": [f[0] for f in found], "scores": [f[1] for f in found], "labels": [f[2] for f in found]}


def test_dino_looks_for_the_prompts_as_lowercase_phrases_on_the_original_photo():
    dino = FakeDino(dino_result())
    dino.annotate(jpeg((200, 100)), CLASSES, PROMPTS, ["", ""], "")
    assert dino.asked == [{"loaded": "dino", "size": (200, 100), "text": "red tin can . glass jar ."}]


def test_dino_turns_pixel_boxes_into_0_1_boxes_of_the_matched_class_with_their_confidence():
    dino = FakeDino(dino_result(([20, 10, 100, 50], 0.9, "red tin can"), ([100, 0, 200, 100], 0.5, "glass jar"),
                                ([0, 0, 10, 10], 0.8, "banana")))
    boxes, unknown = dino.annotate(jpeg((200, 100)), CLASSES, PROMPTS, ["", ""], "")
    assert boxes == [{"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5, "conf": 0.9},
                     {"cls": 1, "x1": 0.5, "y1": 0.0, "x2": 1.0, "y2": 1.0, "conf": 0.5}]
    assert unknown == {"banana"}


def test_dino_drops_a_duplicate_box_on_the_same_object():
    dino = FakeDino(dino_result(([20, 10, 100, 50], 0.6, "red tin can"), ([21, 10, 100, 51], 0.9, "red tin can")))
    boxes, _ = dino.annotate(jpeg((200, 100)), CLASSES, PROMPTS, ["", ""], "")
    assert [b["conf"] for b in boxes] == [0.9]


def test_dino_loads_its_model_once_for_many_photos():
    dino = FakeDino(dino_result())
    dino.annotate(jpeg(), CLASSES, PROMPTS, ["", ""], "")
    dino.annotate(jpeg(), CLASSES, PROMPTS, ["", ""], "")
    assert dino.loads == 1


def test_dino_defaults_and_flags():
    assert (GroundingDinoEngine().model, GroundingDinoEngine().threshold) == (DINO_MODEL, 0.35)
    assert DINO_MODEL == "IDEA-Research/grounding-dino-tiny"
    g = GroundingDinoEngine
    assert (g.name, g.supports_refine, g.resize_input, g.grid) == ("grounding_dino", False, False, False)


# ---------- YOLO-World / YOLOE ----------
class Values(list):
    def tolist(self):
        return list(self)


class FakeYoloModel:
    """Ultralytics' YOLOWorld: set_classes, predict -> [result with boxes.xyxyn / cls / conf]."""

    def __init__(self, found=()):
        self.found = list(found)        # (xyxyn, class position, conf)
        self.classes, self.predicted = [], []

    def set_classes(self, names, embeddings=None):
        self.classes.append((names, embeddings))

    def get_text_pe(self, names):
        return f"embeddings of {names}"

    def predict(self, image, **kw):
        self.predicted.append({"size": image.size, **kw})
        boxes = SimpleNamespace(xyxyn=Values(f[0] for f in self.found), cls=Values(float(f[1]) for f in self.found),
                                conf=Values(f[2] for f in self.found))
        return [SimpleNamespace(boxes=boxes)]


class FakeYolo(YoloWorldEngine):
    def __init__(self, model, yoloe=False, cache=None, cuda=False, **kw):
        super().__init__(cache=cache or ModelCache(free=lambda: None), cuda=lambda: cuda, **kw)
        self.fake, self.yoloe, self.loads = model, yoloe, 0

    def _load(self):
        self.loads += 1
        return {"model": self.fake, "classes": None, "yoloe": self.yoloe}


def test_yolo_looks_for_the_lowercase_prompts_and_only_sets_them_again_when_they_change():
    model = FakeYoloModel()
    yolo = FakeYolo(model)
    yolo.annotate(jpeg(), CLASSES, PROMPTS, ["", ""], "")
    yolo.annotate(jpeg(), CLASSES, PROMPTS, ["", ""], "")
    yolo.annotate(jpeg(), ["jar"], ["glass jar"], [""], "")
    assert model.classes == [(["red tin can", "glass jar"], None), (["glass jar"], None)]
    assert yolo.loads == 1


def test_yoloe_gets_text_embeddings_with_its_classes():
    model = FakeYoloModel()
    FakeYolo(model, yoloe=True).annotate(jpeg(), CLASSES, PROMPTS, ["", ""], "")
    assert model.classes == [(["red tin can", "glass jar"], "embeddings of ['red tin can', 'glass jar']")]


def test_yolo_runs_on_the_original_photo_with_the_confidence_and_half_precision_on_a_gpu():
    model = FakeYoloModel()
    FakeYolo(model, cuda=True, threshold=0.4).annotate(jpeg((200, 100)), CLASSES, PROMPTS, ["", ""], "")
    assert model.predicted == [{"size": (200, 100), "conf": 0.4, "verbose": False, "half": True}]


def test_yolo_boxes_are_already_0_1_and_duplicates_are_dropped():
    model = FakeYoloModel([([0.1, 0.1, 0.5, 0.5], 0, 0.9), ([0.1, 0.1, 0.5, 0.51], 0, 0.3),
                           ([0.6, 0.2, 0.9, 0.8], 1, 0.7)])
    boxes, unknown = FakeYolo(model).annotate(jpeg(), CLASSES, PROMPTS, ["", ""], "")
    assert boxes == [{"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5, "conf": 0.9},
                     {"cls": 1, "x1": 0.6, "y1": 0.2, "x2": 0.9, "y2": 0.8, "conf": 0.7}]
    assert unknown == set()


def test_yolo_defaults_and_flags():
    assert (YoloWorldEngine().model, YoloWorldEngine().threshold) == (YOLO_MODEL, 0.25)
    assert YOLO_MODEL == "yolov8s-worldv2.pt"
    y = YoloWorldEngine
    assert (y.name, y.supports_refine, y.resize_input, y.grid) == ("yolo_world", False, False, False)


def test_both_detectors_share_one_loaded_model():
    cache = ModelCache(free=lambda: None)
    dino, yolo = FakeDino(dino_result(), cache=cache), FakeYolo(FakeYoloModel(), cache=cache)
    dino.annotate(jpeg(), CLASSES, PROMPTS, ["", ""], "")
    yolo.annotate(jpeg(), CLASSES, PROMPTS, ["", ""], "")
    dino.annotate(jpeg(), CLASSES, PROMPTS, ["", ""], "")
    assert (dino.loads, yolo.loads) == (2, 1)
