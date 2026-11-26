"""Grounding DINO through Hugging Face transformers: free, offline, tight boxes. Moved from backends.py.

Runs on the original photo (no shrinking, no grid) and can't refine. What changed: the photo arrives as bytes, and
the model call (`_load`, `_detect`, the only parts that need torch) is split from turning its answer into boxes.
"""
import io

from PIL import Image

from annotator.engine.detectors.common import MODELS, ModelCache, match_class
from annotator.engine.geometry import nms

DEFAULT_MODEL = "IDEA-Research/grounding-dino-tiny"
DEFAULT_THRESHOLD = 0.35


class GroundingDinoEngine:
    name = "grounding_dino"
    label = "Grounding DINO"
    supports_refine = False
    resize_input = False
    grid = False

    def __init__(self, model: str = DEFAULT_MODEL, threshold: float = DEFAULT_THRESHOLD, text_threshold: float = 0.25,
                 *, cache: ModelCache = MODELS):
        self.model = (model or DEFAULT_MODEL).strip()
        self.threshold = float(threshold)
        self.text_threshold = float(text_threshold)
        self.cache = cache

    def _load(self):
        import torch
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        proc = AutoProcessor.from_pretrained(self.model)
        model = AutoModelForZeroShotObjectDetection.from_pretrained(self.model).to(dev).eval()
        return proc, model, dev

    def _detect(self, loaded, image: Image.Image, text: str) -> dict:
        """{"boxes": [[x1, y1, x2, y2] in pixels], "scores": [...], "labels": [text]} from the model."""
        import torch
        proc, model, dev = loaded
        inputs = proc(images=image, text=text, return_tensors="pt").to(dev)
        with torch.no_grad():
            out = model(**inputs)
        kw = dict(text_threshold=self.text_threshold, target_sizes=[(image.height, image.width)])
        try:  # the argument's name changed between transformers versions
            res = proc.post_process_grounded_object_detection(out, inputs.input_ids, threshold=self.threshold, **kw)[0]
        except TypeError:
            res = proc.post_process_grounded_object_detection(out, inputs.input_ids, box_threshold=self.threshold,
                                                              **kw)[0]
        labels = res.get("text_labels", res.get("labels"))
        return {"boxes": res["boxes"].tolist(), "scores": res["scores"].tolist(),
                "labels": [lab if isinstance(lab, str) else str(lab) for lab in labels]}

    def annotate(self, image: bytes, classes, prompts, descs, extra):
        img = Image.open(io.BytesIO(image)).convert("RGB")
        w, h = img.size
        text = " . ".join(p.lower() for p in prompts) + " ."   # Grounding DINO wants lowercase phrases split by " . "
        found = self._detect(self.cache.get(("gdino", self.model), self._load), img, text)
        boxes, unknown = [], set()
        for box, score, lab in zip(found["boxes"], found["scores"], found["labels"], strict=True):
            idx = match_class(lab, prompts)
            if idx is None:
                unknown.add(lab)
                continue
            x1, y1, x2, y2 = box
            boxes.append({"cls": idx, "x1": x1 / w, "y1": y1 / h, "x2": x2 / w, "y2": y2 / h, "conf": float(score)})
        return nms(boxes), unknown
