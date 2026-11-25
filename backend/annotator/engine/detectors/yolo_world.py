"""YOLO-World (yolov8s-worldv2.pt) or YOLOE (yoloe-*.pt) through Ultralytics: free, offline, fastest.
Moved from backends.py.

Runs on the original photo (no shrinking, no grid) and can't refine. What changed: the photo arrives as bytes and is
passed to Ultralytics as a PIL image, and the GPU check is injectable for tests.
"""
import io
from collections.abc import Callable

from PIL import Image

from annotator.engine.detectors.common import MODELS, ModelCache, cuda_available
from annotator.engine.geometry import nms

DEFAULT_MODEL = "yolov8s-worldv2.pt"
DEFAULT_THRESHOLD = 0.25


class YoloWorldEngine:
    name = "yolo_world"
    label = "YOLO-World"
    supports_refine = False
    resize_input = False
    grid = False

    def __init__(self, model: str = DEFAULT_MODEL, threshold: float = DEFAULT_THRESHOLD, *,
                 cache: ModelCache = MODELS, cuda: Callable[[], bool] = cuda_available):
        self.model = (model or DEFAULT_MODEL).strip()
        self.threshold = float(threshold)
        self.cache = cache
        self.cuda = cuda

    def _load(self) -> dict:
        if "yoloe" in self.model.lower():
            from ultralytics import YOLOE
            return {"model": YOLOE(self.model), "classes": None, "yoloe": True}
        from ultralytics import YOLOWorld
        return {"model": YOLOWorld(self.model), "classes": None, "yoloe": False}

    def annotate(self, image: bytes, classes, prompts, descs, extra):
        state = self.cache.get(("yolo", self.model), self._load)
        names = [p.lower() for p in prompts]
        model = state["model"]
        if state["classes"] != names:
            if state["yoloe"]:
                try:
                    model.set_classes(names, model.get_text_pe(names))
                except (AttributeError, TypeError):
                    model.set_classes(names)
            else:
                model.set_classes(names)
            state["classes"] = names
        img = Image.open(io.BytesIO(image)).convert("RGB")
        r = model.predict(img, conf=self.threshold, verbose=False, half=self.cuda())[0]
        boxes = [{"cls": int(c), "x1": xyxyn[0], "y1": xyxyn[1], "x2": xyxyn[2], "y2": xyxyn[3], "conf": float(conf)}
                 for xyxyn, c, conf in zip(r.boxes.xyxyn.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist())]
        return nms(boxes), set()
