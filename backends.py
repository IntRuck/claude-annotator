"""
Labeling backends.

Every backend has the same shape:

    annotate(image_path, classes, prompts, extra, grid, descs=None) -> (boxes, unknown_names)
    refine(clean_path, overlay_path, classes, prompts, current, extra, descs=None) -> (boxes, unknown_names)  # VLMs only

`boxes` is a list of dicts {"cls": int, "x1", "y1", "x2", "y2": floats 0-1, "conf": optional}.
`classes` are the YOLO class names, `prompts` are the text the model should look for
(same as the name unless classes.txt gives a "name | prompt" alias).

Backends:
    claude          Claude Code CLI on your Claude plan login (no API key)
    gemini          Gemini API with a Google AI Studio key (free tier if no billing is linked)
    ollama          Local VLM served by Ollama (e.g. qwen3-vl, qwen2.5vl) - free, offline
    grounding_dino  Grounding DINO via Hugging Face transformers - free, offline, tight boxes
    yolo_world      YOLO-World / YOLOE via Ultralytics - free, offline, fastest

Heavy libraries (torch, transformers, ultralytics) are imported only when that
backend is used, so the Claude option works without them installed.
"""
import base64
import importlib.util
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request

from PIL import Image


class LimitReached(Exception):
    """Raised when Claude reports a usage limit, so the worker can pause."""


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------
def iou(a, b):
    ix = max(0.0, min(a["x2"], b["x2"]) - max(a["x1"], b["x1"]))
    iy = max(0.0, min(a["y2"], b["y2"]) - max(a["y1"], b["y1"]))
    inter = ix * iy
    ua = (a["x2"] - a["x1"]) * (a["y2"] - a["y1"]) + (b["x2"] - b["x1"]) * (b["y2"] - b["y1"]) - inter
    return inter / ua if ua > 0 else 0.0


def nms(boxes, thr=0.6):
    """Drop same-class boxes that overlap a higher-confidence box (detectors often duplicate)."""
    keep = []
    for b in sorted(boxes, key=lambda x: -x.get("conf", 1.0)):
        if all(k["cls"] != b["cls"] or iou(k, b) < thr for k in keep):
            keep.append(b)
    return keep


def to_1000(boxes, classes):
    return [{"class": classes[b["cls"]] if b["cls"] < len(classes) else str(b["cls"]),
             "box": [round(b["x1"] * 1000), round(b["y1"] * 1000),
                     round(b["x2"] * 1000), round(b["y2"] * 1000)]} for b in boxes]


# --------------------------------------------------------------------------
# Prompts for VLM backends (Claude, Ollama)
# --------------------------------------------------------------------------
RULES = """Rules:
- One box per visible object instance. Never split one object into several boxes.
- Each box tightly covers the full visible extent of that object (no padding, nothing cut off).
- Boxes may overlap. An object in front gets its full box even if it overlaps boxes of objects behind it.
- Objects partly hidden behind others: box only the visible part.
- Label every instance of a listed class, including small, partly hidden or edge-of-image ones.
- Ignore objects that do not match any listed class.
- Coordinates are integers on a 0-1000 scale relative to image width and height: [x1, y1, x2, y2], x from left to right, y from top to bottom."""

OUTPUT = """Reply with ONLY this JSON, no other text:
{"objects": [{"class": "<class name>", "box": [x1, y1, x2, y2]}]}
If nothing matches, reply {"objects": []}"""


def class_block(classes, prompts, descs=None):
    """Class list for VLM prompts. A description (from the SKU manager) beats the short prompt."""
    descs = descs or [""] * len(classes)
    lines = []
    for c, p, d in zip(classes, prompts, descs):
        if d:
            lines.append(f"- {c}: {d}")
        elif p and p != c.replace("_", " "):
            lines.append(f"- {c}  (looks like: {p})")
        else:
            lines.append(f"- {c}")
    return "\n".join(lines)


def annotate_prompt(image_ref, classes, prompts, extra, grid, descs=None, rules=RULES, output=OUTPUT):
    g = ("\nThe image has a faint grid every 100 units with labels on the top and left edges. "
         "Use it to read coordinates accurately; the grid is not an object.") if grid else ""
    return f"""{image_ref}
You are labeling this image for an object detection training dataset.{g}

Classes (use these exact names; descriptions say what each one looks like, use them to tell similar products apart):
{class_block(classes, prompts, descs)}

{rules}
{('Extra instructions: ' + extra) if extra else ''}

{output}"""


def refine_prompt(image_ref, classes, prompts, current, extra, descs=None, rules=RULES, output=OUTPUT):
    return f"""{image_ref}
Image 1 is the original. Image 2 is the same image with the current boxes drawn and numbered #0, #1, ...
You are reviewing labels for an object detection training dataset.

Classes (use these exact names; descriptions say what each one looks like, use them to tell similar products apart):
{class_block(classes, prompts, descs)}

Current boxes (index matches the # on image 2, same coordinate format as your answer):
{json.dumps(current)}

Fix every problem you can see: loose or cut-off boxes, one object split into several boxes,
duplicate boxes on the same object, wrong class names, and missing objects. Keep correct boxes as they are.

{rules}
{('Extra instructions: ' + extra) if extra else ''}

Return the complete corrected list (not just the changes).
{output}"""


def parse_objects(text, classes, img_size=None):
    """Turn a VLM reply into normalized boxes. Ignores class names not in the list."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("No JSON in reply: " + text[:200])
    data = json.loads(m.group(0))
    objs = data.get("objects", []) if isinstance(data, dict) else data
    lower = {c.lower(): i for i, c in enumerate(classes)}
    raw = []
    unknown = set()
    for o in objs:
        name = str(o.get("class", o.get("label", ""))).strip()
        idx = lower.get(name.lower())
        if idx is None:
            unknown.add(name)
            continue
        raw.append((idx, [float(v) for v in (o.get("box") or o.get("bbox_2d") or o.get("bbox"))[:4]]))
    # Coordinates are on a 0-1000 scale (Ollama images are sent as 1000x1000, so pixel
    # answers land on the same scale). img_size is kept for callers that send other sizes.
    scale_x = scale_y = 1000.0
    if img_size and img_size != (1000, 1000) and any(v > 1000 for _, b in raw for v in b):
        scale_x, scale_y = float(img_size[0]), float(img_size[1])
    boxes = [{"cls": i, "x1": b[0] / scale_x, "y1": b[1] / scale_y,
              "x2": b[2] / scale_x, "y2": b[3] / scale_y} for i, b in raw]
    return boxes, unknown


# --------------------------------------------------------------------------
# Claude (Claude Code CLI on your plan login)
# --------------------------------------------------------------------------
LIMIT_PAT = re.compile(r"(usage limit|limit reached|5-hour limit|weekly limit|rate limit)", re.I)


def find_claude():
    return os.environ.get("CLAUDE_BIN") or shutil.which("claude") or shutil.which("claude.cmd") or "claude"


class ClaudeBackend:
    name = "claude"
    supports_refine = True
    uses_grid = True
    resize_input = True

    def __init__(self, model="sonnet", timeout=300):
        self.model = model
        self.timeout = timeout

    def _call(self, prompt, workdir):
        cmd = [find_claude(), "-p", prompt, "--output-format", "json",
               "--allowedTools", "Read", "--max-turns", "6", "--add-dir", str(workdir)]
        if self.model:
            cmd += ["--model", self.model]
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)  # use the Claude plan login, never a paid API key
        proc = subprocess.run(cmd, cwd=str(workdir), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=self.timeout, env=env)
        out, err = (proc.stdout or "").strip(), (proc.stderr or "").strip()
        text, is_error = out, proc.returncode != 0
        try:
            data = json.loads(out)
            text = data.get("result") or ""
            is_error = is_error or bool(data.get("is_error"))
        except Exception:
            pass
        if LIMIT_PAT.search(text) or LIMIT_PAT.search(err):
            raise LimitReached((text or err)[:300])
        if is_error and not text:
            raise RuntimeError((err or out or "claude exited with an error")[:500])
        return text

    def annotate(self, image_path, classes, prompts, extra, grid, descs=None):
        ref = f"Use the Read tool to open the image file: {image_path.name}\n"
        text = self._call(annotate_prompt(ref, classes, prompts, extra, grid, descs), image_path.parent)
        return parse_objects(text, classes)

    def refine(self, clean_path, overlay_path, classes, prompts, current, extra, descs=None):
        ref = (f"Use the Read tool to open two images:\n1. {clean_path.name}\n2. {overlay_path.name}\n")
        text = self._call(refine_prompt(ref, classes, prompts, current, extra, descs), clean_path.parent)
        return parse_objects(text, classes)


# --------------------------------------------------------------------------
# Ollama (local VLM, e.g. qwen3-vl / qwen2.5vl / gemma3)
# --------------------------------------------------------------------------
class OllamaBackend:
    name = "ollama"
    supports_refine = True
    uses_grid = True
    resize_input = True

    def __init__(self, model="qwen3-vl:4b", url="http://127.0.0.1:11434", timeout=600):
        self.model = model
        self.url = url.rstrip("/")
        self.timeout = timeout

    def _chat(self, prompt, image_paths):
        imgs = [base64.b64encode(p.read_bytes()).decode() for p in image_paths]
        body = {"model": self.model, "stream": False, "format": "json",
                "options": {"temperature": 0},
                "messages": [{"role": "user", "content": prompt, "images": imgs}]}
        req = urllib.request.Request(self.url + "/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read().decode())
        except urllib.error.URLError as e:
            raise RuntimeError(f"Ollama not reachable at {self.url} ({e}). Is 'ollama serve' running "
                               f"and is the model pulled ('ollama pull {self.model}')?")
        if "error" in data:
            raise RuntimeError("Ollama: " + str(data["error"]))
        return data.get("message", {}).get("content", "")

    # Local models disagree on coordinates: some answer on a 0-1000 scale (Qwen3-VL),
    # others in pixels (Qwen2.5-VL). Sending a 1000x1000 letterboxed image makes the two
    # the same, so either answer maps back correctly.
    @staticmethod
    def _letterbox(path):
        im = Image.open(path).convert("RGB")
        s = 1000 / max(im.size)
        w, h = round(im.width * s), round(im.height * s)
        canvas = Image.new("RGB", (1000, 1000), (114, 114, 114))
        ox, oy = (1000 - w) // 2, (1000 - h) // 2
        canvas.paste(im.resize((w, h), Image.LANCZOS), (ox, oy))
        out = path.with_name(path.stem + "__lb.jpg")
        canvas.save(out, quality=92)
        return out, (ox, oy, w, h)

    @staticmethod
    def _unbox(boxes, geo):
        ox, oy, w, h = geo
        return [{**b, "x1": (b["x1"] * 1000 - ox) / w, "x2": (b["x2"] * 1000 - ox) / w,
                 "y1": (b["y1"] * 1000 - oy) / h, "y2": (b["y2"] * 1000 - oy) / h} for b in boxes]

    def annotate(self, image_path, classes, prompts, extra, grid, descs=None):
        lb, geo = self._letterbox(image_path)
        note = "\nThe image is padded with grey bars to a square; ignore the bars."
        text = self._chat(annotate_prompt("", classes, prompts, extra + note if extra else note.strip(), grid, descs), [lb])
        boxes, unknown = parse_objects(text, classes, (1000, 1000))
        return self._unbox(boxes, geo), unknown

    def refine(self, clean_path, overlay_path, classes, prompts, current, extra, descs=None):
        lb_clean, geo = self._letterbox(clean_path)
        lb_over, _ = self._letterbox(overlay_path)
        ox, oy, w, h = geo
        cur = [{"class": c["class"], "box": [round(ox + c["box"][0] / 1000 * w), round(oy + c["box"][1] / 1000 * h),
                                              round(ox + c["box"][2] / 1000 * w), round(oy + c["box"][3] / 1000 * h)]}
               for c in current]
        text = self._chat(refine_prompt("", classes, prompts, cur, extra, descs), [lb_clean, lb_over])
        boxes, unknown = parse_objects(text, classes, (1000, 1000))
        return self._unbox(boxes, geo), unknown


def ollama_status(url="http://127.0.0.1:11434"):
    """Return list of installed Ollama model names, or None if Ollama isn't running."""
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=0.8) as r:
            return [m["name"] for m in json.loads(r.read().decode()).get("models", [])]
    except Exception:
        return None


# --------------------------------------------------------------------------
# Gemini (Google AI Studio API key; free tier if no billing is linked)
# --------------------------------------------------------------------------
GEMINI_URL = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")  # override only for testing

# Gemini is trained to answer boxes as box_2d = [ymin, xmin, ymax, xmax] on 0-1000.
# We ask for its native format (y first!) and swap to x-first when parsing.
GEMINI_RULES = RULES.replace(
    "- Coordinates are integers on a 0-1000 scale relative to image width and height: "
    "[x1, y1, x2, y2], x from left to right, y from top to bottom.",
    "- box_2d is [ymin, xmin, ymax, xmax]: integers normalized to 0-1000 relative to image "
    "height (y) and width (x). y comes first.")
GEMINI_OUTPUT = """Reply with JSON: {"objects": [{"label": "<class name>", "box_2d": [ymin, xmin, ymax, xmax]}]}
If nothing matches, reply {"objects": []}"""


def gemini_key():
    return (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()


class GeminiBackend:
    name = "gemini"
    supports_refine = True
    uses_grid = False      # Gemini has native box training; a grid would only get in the way
    resize_input = True

    def __init__(self, model="gemini-3.5-flash-lite", timeout=180):
        self.model = model.strip().removeprefix("models/")
        self.timeout = timeout

    def _schema(self, classes):
        return {"type": "OBJECT", "properties": {"objects": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {"label": {"type": "STRING", "enum": list(classes)},   # only your class names
                           "box_2d": {"type": "ARRAY", "items": {"type": "INTEGER"}}},
            "required": ["label", "box_2d"]}}},
            "required": ["objects"]}

    def _post(self, prompt, image_paths, classes):
        key = gemini_key()
        if not key:
            raise RuntimeError("No Gemini API key. Put GEMINI_API_KEY=... in a .env file next to app.py "
                               "(see README), then restart the app.")
        parts = [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(p.read_bytes()).decode()}}
                 for p in image_paths]
        parts.append({"text": prompt})
        body = {"contents": [{"parts": parts}],
                "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                                     "responseSchema": self._schema(classes)}}
        url = f"{GEMINI_URL}/models/{self.model}:generateContent"
        data = json.dumps(body).encode()
        for attempt in range(4):
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json",
                                                                   "x-goog-api-key": key})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                try:
                    err = json.loads(e.read().decode()).get("error", {})
                except Exception:
                    err = {}
                msg = err.get("message", str(e))
                if e.code == 429:
                    details = json.dumps(err.get("details", []))
                    if "PerDay" in details or "per day" in msg.lower():
                        raise LimitReached(f"Gemini daily free quota used up for {self.model}. "
                                           f"It resets tomorrow; or switch to another model. ({msg[:150]})")
                    wait = _retry_delay(err) + 2           # per-minute limit: wait and try again
                    if attempt < 3 and wait <= 90:
                        time.sleep(wait)
                        continue
                    raise LimitReached(f"Gemini rate limit: {msg[:200]}")
                if e.code == 402:
                    raise LimitReached("Gemini prepaid credit is empty (this key is on a paid project).")
                if e.code in (500, 503) and attempt < 3:
                    time.sleep(5 * (attempt + 1))           # model overloaded: back off a bit
                    continue
                if e.code == 404:
                    raise RuntimeError(f"Gemini model '{self.model}' not found for this key. Pick one from "
                                       f"the list in the app. ({msg[:150]})")
                raise RuntimeError(f"Gemini HTTP {e.code}: {msg[:300]}")
            except urllib.error.URLError as e:
                raise RuntimeError(f"Can't reach the Gemini API ({e.reason}). Check your internet connection.")
        raise RuntimeError("Gemini: too many retries")

    @staticmethod
    def _text(resp):
        cands = resp.get("candidates") or []
        if not cands:
            reason = (resp.get("promptFeedback") or {}).get("blockReason", "no answer")
            raise RuntimeError(f"Gemini returned no result ({reason})")
        parts = (cands[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))

    @staticmethod
    def _parse(text, classes):
        """box_2d is [ymin, xmin, ymax, xmax] on 0-1000 -> our x-first normalized boxes."""
        m = re.search(r"\{.*\}|\[.*\]", text, re.S)
        if not m:
            raise ValueError("No JSON in Gemini reply: " + text[:200])
        data = json.loads(m.group(0))
        objs = data.get("objects", []) if isinstance(data, dict) else data
        lower = {c.lower(): i for i, c in enumerate(classes)}
        boxes, unknown = [], set()
        for o in objs:
            name = str(o.get("label", o.get("class", ""))).strip()
            idx = lower.get(name.lower())
            b = o.get("box_2d") or []
            if idx is None:
                unknown.add(name)
                continue
            if len(b) != 4:
                continue
            ymin, xmin, ymax, xmax = [float(v) for v in b]
            boxes.append({"cls": idx, "x1": xmin / 1000, "y1": ymin / 1000, "x2": xmax / 1000, "y2": ymax / 1000})
        return boxes, unknown

    def annotate(self, image_path, classes, prompts, extra, grid, descs=None):
        prompt = annotate_prompt("", classes, prompts, extra, False, descs, GEMINI_RULES, GEMINI_OUTPUT)
        return self._parse(self._text(self._post(prompt, [image_path], classes)), classes)

    def refine(self, clean_path, overlay_path, classes, prompts, current, extra, descs=None):
        # current comes in x-first; show it to Gemini in its own y-first format
        cur = [{"label": c["class"], "box_2d": [c["box"][1], c["box"][0], c["box"][3], c["box"][2]]} for c in current]
        prompt = refine_prompt("", classes, prompts, cur, extra, descs, GEMINI_RULES, GEMINI_OUTPUT)
        return self._parse(self._text(self._post(prompt, [clean_path, overlay_path], classes)), classes)


def _retry_delay(err):
    for d in err.get("details", []) or []:
        rd = d.get("retryDelay")
        if rd:
            try:
                return float(str(rd).rstrip("s"))
            except ValueError:
                pass
    return 30.0


_gemini_models_cache = {}


def gemini_models():
    """Model names this key can use for generateContent (cached per key). None if no key / unreachable."""
    key = gemini_key()
    if not key:
        return None
    if key in _gemini_models_cache:
        return _gemini_models_cache[key]
    try:
        req = urllib.request.Request(f"{GEMINI_URL}/models?pageSize=200", headers={"x-goog-api-key": key})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
        names = sorted(m["name"].removeprefix("models/") for m in data.get("models", [])
                       if "generateContent" in m.get("supportedGenerationMethods", [])
                       and "gemini" in m.get("name", "")
                       and not any(x in m["name"] for x in ("tts", "image", "embedding", "live", "audio")))
    except Exception:
        names = []
    _gemini_models_cache[key] = names
    return names


# --------------------------------------------------------------------------
# Open-vocabulary detectors (text prompt -> boxes). Only one stays loaded at a time
# so a 4 GB GPU doesn't run out of memory.
# --------------------------------------------------------------------------
_loaded = {"key": None, "obj": None}


def _free_gpu():
    _loaded["key"], _loaded["obj"] = None, None
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _get_cached(key, loader):
    if _loaded["key"] != key:
        _free_gpu()
        _loaded["obj"] = loader()
        _loaded["key"] = key
    return _loaded["obj"]


def _match_class(label, prompts):
    """Map a detector's text label back to a class index."""
    label = (label or "").strip().lower()
    low = [p.lower() for p in prompts]
    if label in low:
        return low.index(label)
    best, best_len = None, 0
    for i, p in enumerate(low):
        if p in label or label in p:
            overlap = min(len(p), len(label))
            if overlap > best_len:
                best, best_len = i, overlap
    return best


class GroundingDinoBackend:
    name = "grounding_dino"
    supports_refine = False
    uses_grid = False
    resize_input = False

    def __init__(self, model_id="IDEA-Research/grounding-dino-tiny", threshold=0.35, text_threshold=0.25):
        self.model_id = model_id
        self.threshold = float(threshold)
        self.text_threshold = float(text_threshold)

    def _load(self):
        import torch
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        proc = AutoProcessor.from_pretrained(self.model_id)
        model = AutoModelForZeroShotObjectDetection.from_pretrained(self.model_id).to(dev).eval()
        return proc, model, dev

    def annotate(self, image_path, classes, prompts, extra, grid, descs=None):
        import torch
        proc, model, dev = _get_cached(("gdino", self.model_id), self._load)
        img = Image.open(image_path).convert("RGB")
        W, H = img.size
        # Grounding DINO wants lowercase phrases separated by " . "
        text = " . ".join(p.lower() for p in prompts) + " ."
        inputs = proc(images=img, text=text, return_tensors="pt").to(dev)
        with torch.no_grad():
            out = model(**inputs)
        kw = dict(text_threshold=self.text_threshold, target_sizes=[(H, W)])
        try:  # argument name changed between transformers versions
            res = proc.post_process_grounded_object_detection(out, inputs.input_ids, threshold=self.threshold, **kw)[0]
        except TypeError:
            res = proc.post_process_grounded_object_detection(out, inputs.input_ids, box_threshold=self.threshold, **kw)[0]
        labels = res.get("text_labels", res.get("labels"))
        boxes, unknown = [], set()
        for box, score, lab in zip(res["boxes"].tolist(), res["scores"].tolist(), labels):
            idx = _match_class(lab if isinstance(lab, str) else str(lab), prompts)
            if idx is None:
                unknown.add(str(lab))
                continue
            x1, y1, x2, y2 = box
            boxes.append({"cls": idx, "x1": x1 / W, "y1": y1 / H, "x2": x2 / W, "y2": y2 / H, "conf": float(score)})
        return nms(boxes), unknown


class YoloWorldBackend:
    """YOLO-World (yolov8s-worldv2.pt) or YOLOE (yoloe-*.pt) through Ultralytics."""
    name = "yolo_world"
    supports_refine = False
    uses_grid = False
    resize_input = False

    def __init__(self, weights="yolov8s-worldv2.pt", threshold=0.25):
        self.weights = weights
        self.threshold = float(threshold)

    def _load(self):
        if "yoloe" in self.weights.lower():
            from ultralytics import YOLOE
            return {"model": YOLOE(self.weights), "classes": None, "yoloe": True}
        from ultralytics import YOLOWorld
        return {"model": YOLOWorld(self.weights), "classes": None, "yoloe": False}

    def annotate(self, image_path, classes, prompts, extra, grid, descs=None):
        import torch
        st = _get_cached(("yolo", self.weights), self._load)
        names = [p.lower() for p in prompts]
        if st["classes"] != names:
            m = st["model"]
            if st["yoloe"]:
                try:
                    m.set_classes(names, m.get_text_pe(names))
                except (AttributeError, TypeError):
                    m.set_classes(names)
            else:
                m.set_classes(names)
            st["classes"] = names
        r = st["model"].predict(str(image_path), conf=self.threshold, verbose=False,
                                half=torch.cuda.is_available())[0]
        boxes = []
        for xyxyn, c, conf in zip(r.boxes.xyxyn.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist()):
            boxes.append({"cls": int(c), "x1": xyxyn[0], "y1": xyxyn[1], "x2": xyxyn[2], "y2": xyxyn[3],
                          "conf": float(conf)})
        return nms(boxes), set()


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------
def make_backend(name, opts):
    if name == "ollama":
        return OllamaBackend(opts.get("ollama_model") or "qwen3-vl:4b",
                             opts.get("ollama_url") or "http://127.0.0.1:11434")
    if name == "gemini":
        return GeminiBackend(opts.get("gemini_model") or "gemini-3.5-flash-lite")
    if name == "grounding_dino":
        return GroundingDinoBackend(opts.get("gdino_model") or "IDEA-Research/grounding-dino-tiny",
                                    opts.get("threshold", 0.35))
    if name == "yolo_world":
        return YoloWorldBackend(opts.get("yolo_weights") or "yolov8s-worldv2.pt",
                                opts.get("threshold", 0.25))
    return ClaudeBackend(opts.get("model") or "sonnet")


_cuda_cache = {}


def availability(check_cuda=True):
    """What's installed, so the UI can show it. Importing torch takes seconds, so the CUDA
    check is optional and cached after the first time."""
    has = lambda m: importlib.util.find_spec(m) is not None
    cuda = _cuda_cache.get("v")
    if check_cuda and cuda is None:
        cuda = False
        if has("torch"):
            try:
                import torch
                cuda = torch.cuda.is_available()
            except Exception:
                pass
        _cuda_cache["v"] = cuda
    return {
        "claude": bool(shutil.which("claude") or shutil.which("claude.cmd") or os.environ.get("CLAUDE_BIN")),
        "ollama": ollama_status(),
        "gemini_key": bool(gemini_key()),
        "gemini_models": gemini_models() if check_cuda else None,  # network call: skip at startup
        "grounding_dino": has("torch") and has("transformers"),
        "yolo_world": has("ultralytics"),
        "cuda": cuda,
    }
