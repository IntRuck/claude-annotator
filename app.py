"""
Claude Annotator: local dashboard that auto-annotates an image folder for object
detection, with a built-in box editor for manual fixes.

Labeling engines (see backends.py): Claude Code on your Claude plan, a local VLM
through Ollama, Grounding DINO, or YOLO-World / YOLOE.

Run:
    python app.py --images path/to/images --classes classes.txt

Labels are written as YOLO .txt files (class cx cy w h, normalized 0-1).
"""
import argparse
import io
import json
import os
import random
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file
from PIL import Image, ImageDraw, ImageFont

from backends import LimitReached, availability, find_claude, iou, make_backend, to_1000

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
MAX_SIDE = 1568  # Claude's native max image side; bigger gets downscaled anyway


# --------------------------------------------------------------------------
# Project storage
# --------------------------------------------------------------------------
class Project:
    def __init__(self, images_dir, labels_dir, classes_file):
        self.images_dir = Path(images_dir).resolve()
        self.labels_dir = Path(labels_dir).resolve()
        self.classes_file = Path(classes_file).resolve()
        self.labels_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir = self.labels_dir / "_claude_tmp"
        self.tmp_dir.mkdir(exist_ok=True)
        self.state_file = self.labels_dir / "_annot_state.json"
        self.lock = threading.RLock()
        if not self.classes_file.exists():
            self.classes_file.write_text("", encoding="utf-8")
        self.state = {}
        if self.state_file.exists():
            try:
                self.state = json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                self.state = {}

    # classes -------------------------------------------------------------
    # classes.txt: one class per line. Line number = YOLO class ID.
    # Optional detector prompt after "|", e.g.  "tuna_400g | red tin can"
    # Line format:  name | detector prompt | description   (prompt and description optional)
    #   name        -> the YOLO class name (line number = class ID)
    #   prompt      -> short phrase for Grounding DINO / YOLO-World, e.g. "red tin can"
    #   description -> detailed look for VLMs (Claude, Ollama), e.g. "red round tin, yellow 'SARDIN' label"
    def class_entries(self):
        entries = []
        for line in self.classes_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            parts = [x.strip() for x in line.split("|", 2)] + ["", ""]
            entries.append((parts[0], parts[1], parts[2]))
        return entries

    def classes(self):
        return [e[0] for e in self.class_entries()]

    def prompts(self):
        """Text the detectors search for: the prompt if given, else the name with _ turned into spaces."""
        return [p or n.replace("_", " ") for n, p, _ in self.class_entries()]

    def descriptions(self):
        return [d for _, _, d in self.class_entries()]

    @staticmethod
    def _clean(s):
        return " ".join((s or "").replace("|", "/").split())  # one line, no separator characters

    def _write_entries(self, entries):
        lines = []
        for n, p, d in entries:
            if d:
                lines.append(f"{n} | {p} | {d}")
            elif p:
                lines.append(f"{n} | {p}")
            else:
                lines.append(n)
        self.classes_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def add_class(self, name, prompt="", description=""):
        name = self._clean(name).replace(" ", "_")
        with self.lock:
            entries = self.class_entries()
            if name and name not in [e[0] for e in entries]:
                # always append so existing IDs never shift
                entries.append((name, self._clean(prompt), self._clean(description)))
                self._write_entries(entries)
            return self.classes()

    def update_class(self, idx, name=None, prompt=None, description=None):
        """Change a class's name/prompt/description. The ID (line number) never changes."""
        with self.lock:
            entries = self.class_entries()
            if 0 <= idx < len(entries):
                n, p, d = entries[idx]
                if name is not None and self._clean(name):
                    new = self._clean(name).replace(" ", "_")
                    if new == n or new not in [e[0] for e in entries]:
                        n = new
                if prompt is not None:
                    p = self._clean(prompt)
                if description is not None:
                    d = self._clean(description)
                entries[idx] = (n, p, d)
                self._write_entries(entries)
            return self.classes()

    # images --------------------------------------------------------------
    def images(self):
        return sorted(
            p.name for p in self.images_dir.iterdir()
            if p.is_file() and p.suffix.lower() in IMG_EXT
        )

    def image_path(self, name):
        p = (self.images_dir / name).resolve()
        if p.parent != self.images_dir or not p.exists():
            raise FileNotFoundError(name)
        return p

    def label_path(self, name):
        return self.labels_dir / (Path(name).stem + ".txt")

    # labels --------------------------------------------------------------
    def read_boxes(self, name):
        """Return boxes as dicts with normalized x1,y1,x2,y2 and class id."""
        lp = self.label_path(name)
        boxes = []
        if not lp.exists():
            return boxes
        for line in lp.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            c, cx, cy, w, h = int(float(parts[0])), *map(float, parts[1:5])
            boxes.append({
                "cls": c,
                "x1": cx - w / 2, "y1": cy - h / 2,
                "x2": cx + w / 2, "y2": cy + h / 2,
            })
        return boxes

    def write_boxes(self, name, boxes):
        lines = []
        for b in boxes:
            x1, x2 = sorted((clamp01(b["x1"]), clamp01(b["x2"])))
            y1, y2 = sorted((clamp01(b["y1"]), clamp01(b["y2"])))
            w, h = x2 - x1, y2 - y1
            if w <= 0.001 or h <= 0.001:
                continue
            lines.append(f"{int(b['cls'])} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {w:.6f} {h:.6f}")
        self.label_path(name).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return len(lines)

    # state -----------------------------------------------------------------
    def _save_state(self):
        self.state_file.write_text(json.dumps(self.state, indent=1), encoding="utf-8")

    def set_status(self, name, status, note=""):
        with self.lock:
            entry = self.state.get(name, {})  # update, don't replace, so the flag survives
            entry.update(status=status, note=note, updated=datetime.now().isoformat(timespec="seconds"))
            self.state[name] = entry
            self._save_state()

    # Flag = "check this later". Separate from status, so a reviewed image can still be flagged.
    def set_flag(self, name, flagged, reason="", note=""):
        with self.lock:
            entry = self.state.get(name) or {"status": self.status(name), "note": ""}
            entry.update(flag=bool(flagged), flag_reason=reason if flagged else "",
                         flag_note=note if flagged else "")
            self.state[name] = entry
            self._save_state()

    def flagged(self, name):
        return bool(self.state.get(name, {}).get("flag"))

    def status(self, name):
        s = self.state.get(name)
        if s:
            return s["status"]
        return "auto" if self.label_path(name).exists() else "none"


def clamp01(v):
    return max(0.0, min(1.0, float(v)))


# --------------------------------------------------------------------------
# Image prep for Claude
# --------------------------------------------------------------------------
def _font(size):
    for f in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            pass
    return ImageFont.load_default()


def prep_image(src, dst, grid=False, boxes=None, classes=None):
    """Resize to <= MAX_SIDE, optionally draw a 0-1000 grid and/or numbered boxes."""
    im = Image.open(src).convert("RGB")
    scale = min(1.0, MAX_SIDE / max(im.size))
    if scale < 1.0:
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    W, H = im.size
    draw = ImageDraw.Draw(im, "RGBA")
    if grid:
        f = _font(max(10, W // 90))
        for i in range(1, 10):
            x, y = W * i / 10, H * i / 10
            draw.line([(x, 0), (x, H)], fill=(255, 255, 255, 70), width=1)
            draw.line([(0, y), (W, y)], fill=(255, 255, 255, 70), width=1)
            draw.text((x + 2, 2), str(i * 100), fill=(255, 255, 0, 200), font=f)
            draw.text((2, y + 2), str(i * 100), fill=(255, 255, 0, 200), font=f)
    if boxes:
        f = _font(max(12, W // 60))
        for i, b in enumerate(boxes):
            x1, y1, x2, y2 = b["x1"] * W, b["y1"] * H, b["x2"] * W, b["y2"] * H
            draw.rectangle([x1, y1, x2, y2], outline=(255, 0, 80, 255), width=max(2, W // 400))
            draw.text((x1 + 3, y1 + 2), f"#{i}", fill=(255, 255, 0, 255), font=f,
                      stroke_width=2, stroke_fill=(0, 0, 0, 255))
    im.save(dst, quality=92)
    return W, H


# --------------------------------------------------------------------------
# Background worker: runs the chosen backend over a list of images
# --------------------------------------------------------------------------
class Worker:
    def __init__(self, project):
        self.p = project
        self.thread = None
        self.stop_flag = threading.Event()
        self.queue = []
        self.done = 0
        self.total = 0
        self.current = None
        self.message = "idle"
        self.log = []

    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def _log(self, msg):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        self.log.append(line)
        self.log = self.log[-300:]
        print(line, flush=True)

    def start(self, names, mode, backend_name, opts, grid, extra):
        if self.running():
            return False
        self.stop_flag.clear()
        self.queue = list(names)
        self.done, self.total = 0, len(self.queue)
        self.thread = threading.Thread(target=self._run, args=(mode, backend_name, opts, grid, extra), daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.stop_flag.set()

    def _run(self, mode, backend_name, opts, grid, extra):
        classes, prompts, descs = self.p.classes(), self.p.prompts(), self.p.descriptions()
        if not classes:
            self.message = "No classes defined"
            self._log(self.message)
            return
        backend = make_backend(backend_name, opts)
        if mode == "refine" and not backend.supports_refine:
            self.message = f"{backend.name} can't refine; use Claude or a local VLM"
            self._log(self.message)
            return
        grid = grid and backend.uses_grid
        self._log(f"Start {mode} on {self.total} image(s) with {backend.name} "
                  f"({json.dumps({k: v for k, v in opts.items() if v not in ('', None)})}), grid={grid}")
        for name in self.queue:
            if self.stop_flag.is_set():
                self.message = "stopped"
                self._log("Stopped by user")
                break
            self.current = name
            self.message = f"{mode}: {name}"
            t0 = time.time()
            try:
                if mode == "refine":
                    boxes, unknown = self._refine_one(backend, name, classes, prompts, descs, extra)
                else:
                    boxes, unknown = self._annotate_one(backend, name, classes, prompts, descs, grid, extra)
                n_saved = self.p.write_boxes(name, boxes)
                note = f"via {backend.name}"
                if unknown:
                    note += f"; unknown classes ignored: {', '.join(sorted(unknown))}"
                self.p.set_status(name, "auto", note)
                self._log(f"{name}: {n_saved} box(es) in {time.time() - t0:.1f}s ({note})")
            except LimitReached as e:
                who = {"claude": "Claude usage limit", "gemini": "Gemini quota"}.get(backend.name, "Usage limit")
                self.message = f"{who} reached. Paused; press Annotate again after it resets."
                self._log(f"LIMIT: {e}")
                break
            except Exception as e:
                self.p.set_status(name, "error", f"{backend.name}: {str(e)[:300]}")
                self._log(f"{name}: ERROR {e}")
            self.done += 1
        else:
            self.message = "finished"
        self.current = None
        self._log(f"Done {self.done}/{self.total}")

    def _annotate_one(self, backend, name, classes, prompts, descs, grid, extra):
        src = self.p.image_path(name)
        if getattr(backend, "resize_input", backend.uses_grid):
            # VLMs: send a resized copy (optionally with a grid); originals are never modified
            tmp = self.p.tmp_dir / (Path(name).stem + "__in.jpg")
            prep_image(src, tmp, grid=grid)
            return backend.annotate(tmp, classes, prompts, extra, grid, descs=descs)
        # Detectors: run on the original image for the best box accuracy
        return backend.annotate(src, classes, prompts, extra, False, descs=descs)

    def _refine_one(self, backend, name, classes, prompts, descs, extra):
        src = self.p.image_path(name)
        current = self.p.read_boxes(name)
        clean = self.p.tmp_dir / (Path(name).stem + "__clean.jpg")
        over = self.p.tmp_dir / (Path(name).stem + "__overlay.jpg")
        prep_image(src, clean)
        prep_image(src, over, boxes=current, classes=classes)
        return backend.refine(clean, over, classes, prompts, to_1000(current, classes), extra, descs=descs)

# --------------------------------------------------------------------------
# Dataset health check
# --------------------------------------------------------------------------
def health_report(p, low_count=100, grid=20):
    classes = p.classes()
    nC = len(classes)
    per_class = [{"id": i, "name": c, "boxes": 0, "images": [], "area_sum": 0.0} for i, c in enumerate(classes)]
    status_counts = {}
    size_buckets = {"tiny (<0.1%)": 0, "small (0.1-1%)": 0, "medium (1-10%)": 0, "large (>10%)": 0}
    heat = [[0] * grid for _ in range(grid)]
    issues = {
        "flagged": {"label": "🚩 Flagged by you to check later", "images": []},
        "unlabeled": {"label": "Unlabeled images", "images": []},
        "errors": {"label": "Claude errors", "images": []},
        "empty": {"label": "Labeled but no boxes (background)", "images": []},
        "duplicates": {"label": "Possible duplicate boxes (same class, IoU > 0.85)", "images": []},
        "tiny": {"label": "Tiny boxes (< 0.5% width or height)", "images": []},
        "bad_class": {"label": "Class ID not in class list", "images": []},
        "crowded": {"label": "Very crowded (> 100 boxes)", "images": []},
    }
    total_boxes, labeled = 0, 0
    images = p.images()
    for n in images:
        st = p.status(n)
        status_counts[st] = status_counts.get(st, 0) + 1
        if p.flagged(n):
            issues["flagged"]["images"].append(n)
        if st == "error":
            issues["errors"]["images"].append(n)
        if not p.label_path(n).exists():
            issues["unlabeled"]["images"].append(n)
            continue
        labeled += 1
        boxes = p.read_boxes(n)
        if not boxes:
            issues["empty"]["images"].append(n)
        if len(boxes) > 100:
            issues["crowded"]["images"].append(n)
        total_boxes += len(boxes)
        flags = set()
        for i, b in enumerate(boxes):
            w, h = b["x2"] - b["x1"], b["y2"] - b["y1"]
            area = w * h
            if b["cls"] >= nC or b["cls"] < 0:
                flags.add("bad_class")
            else:
                pc = per_class[b["cls"]]
                pc["boxes"] += 1
                pc["area_sum"] += area
                if not pc["images"] or pc["images"][-1] != n:
                    pc["images"].append(n)
            if w < 0.005 or h < 0.005:
                flags.add("tiny")
            if area < 0.001:
                size_buckets["tiny (<0.1%)"] += 1
            elif area < 0.01:
                size_buckets["small (0.1-1%)"] += 1
            elif area < 0.1:
                size_buckets["medium (1-10%)"] += 1
            else:
                size_buckets["large (>10%)"] += 1
            cx = min(grid - 1, max(0, int((b["x1"] + b["x2"]) / 2 * grid)))
            cy = min(grid - 1, max(0, int((b["y1"] + b["y2"]) / 2 * grid)))
            heat[cy][cx] += 1
            for b2 in boxes[i + 1:]:
                if b2["cls"] == b["cls"] and iou(b, b2) > 0.85:
                    flags.add("duplicates")
        for f in flags:
            issues[f]["images"].append(n)

    nonzero = [c["boxes"] for c in per_class if c["boxes"] > 0]
    classes_out = []
    for c in per_class:
        warn = ""
        if c["boxes"] == 0:
            warn = "no boxes"
        elif c["boxes"] < low_count:
            warn = f"low (< {low_count})"
        classes_out.append({
            "id": c["id"], "name": c["name"], "boxes": c["boxes"], "images": len(c["images"]),
            "avg_area_pct": round(100 * c["area_sum"] / c["boxes"], 2) if c["boxes"] else 0,
            "warn": warn, "image_list": c["images"],
        })
    return {
        "summary": {
            "images": len(images), "labeled": labeled, "boxes": total_boxes,
            "avg_boxes_per_image": round(total_boxes / labeled, 1) if labeled else 0,
            "classes": nC, "classes_with_data": len(nonzero),
            "imbalance_ratio": round(max(nonzero) / min(nonzero), 1) if nonzero else 0,
            "status": status_counts,
        },
        "classes": classes_out,
        "sizes": size_buckets,
        "heatmap": heat,
        "issues": [{"key": k, **v, "count": len(v["images"])} for k, v in issues.items()],
        "low_count": low_count,
    }


# --------------------------------------------------------------------------
# Exports
# --------------------------------------------------------------------------
def export_yolo_zip(p, val_ratio=0.1, only_reviewed=False, seed=0, skip_flagged=False):
    classes = p.classes()
    names = [n for n in p.images() if p.label_path(n).exists()]
    if only_reviewed:
        names = [n for n in names if p.status(n) == "reviewed"]
    if skip_flagged:
        names = [n for n in names if not p.flagged(n)]
    rnd = random.Random(seed)
    rnd.shuffle(names)
    n_val = int(len(names) * val_ratio)
    split = {n: ("val" if i < n_val else "train") for i, n in enumerate(names)}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n, s in split.items():
            z.write(p.image_path(n), f"dataset/images/{s}/{n}")
            z.write(p.label_path(n), f"dataset/labels/{s}/{Path(n).stem}.txt")
        yaml = "path: .\ntrain: images/train\nval: images/val\n\nnames:\n" + \
               "".join(f"  {i}: {c}\n" for i, c in enumerate(classes))
        z.writestr("dataset/data.yaml", yaml)
    buf.seek(0)
    return buf


def export_coco(p, only_reviewed=False, skip_flagged=False):
    classes = p.classes()
    coco = {"images": [], "annotations": [],
            "categories": [{"id": i, "name": c} for i, c in enumerate(classes)]}
    ann_id = 1
    for img_id, n in enumerate(p.images(), start=1):
        if not p.label_path(n).exists():
            continue
        if only_reviewed and p.status(n) != "reviewed":
            continue
        if skip_flagged and p.flagged(n):
            continue
        with Image.open(p.image_path(n)) as im:
            W, H = im.size
        coco["images"].append({"id": img_id, "file_name": n, "width": W, "height": H})
        for b in p.read_boxes(n):
            x, y = b["x1"] * W, b["y1"] * H
            w, h = (b["x2"] - b["x1"]) * W, (b["y2"] - b["y1"]) * H
            coco["annotations"].append({"id": ann_id, "image_id": img_id, "category_id": b["cls"],
                                        "bbox": [round(x, 2), round(y, 2), round(w, 2), round(h, 2)],
                                        "area": round(w * h, 2), "iscrowd": 0})
            ann_id += 1
    return coco


# --------------------------------------------------------------------------
# Web app
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Start page helpers: folder browser, dataset preview, recent datasets
# --------------------------------------------------------------------------
class NoProject(Exception):
    """Raised when an API call needs a dataset but none is open yet."""


RECENT_FILE = Path(__file__).parent / "recent.json"


def _count_images(d):
    try:
        return sum(1 for f in d.iterdir() if f.is_file() and f.suffix.lower() in IMG_EXT)
    except (PermissionError, OSError):
        return 0


def browse_dir(path):
    """List sub-folders of a folder on this computer (the app only listens on 127.0.0.1)."""
    p = Path(path).expanduser() if path else Path.home()
    try:
        p = p.resolve()
    except OSError:
        p = Path.home()
    if not p.is_dir():
        p = p.parent if p.parent.is_dir() else Path.home()
    dirs = []
    try:
        for c in sorted(p.iterdir(), key=lambda x: x.name.lower()):
            if c.is_dir() and not c.name.startswith((".", "$")):
                dirs.append(c.name)
    except (PermissionError, OSError):
        pass
    drives = []
    if os.name == "nt":  # Windows: offer C:\, D:\ ...
        import string
        drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
    return {"path": str(p), "parent": str(p.parent) if p.parent != p else None,
            "dirs": dirs[:500], "image_count": _count_images(p), "home": str(Path.home()), "drives": drives}


def read_yaml_names(path):
    """Class names from a YOLO data.yaml (list or id: name form), without needing PyYAML."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.strip().startswith("names:"):
            continue
        rest = line.split(":", 1)[1].strip()
        if rest.startswith("["):                       # names: [a, b, c]
            return [x.strip().strip("'\"") for x in rest.strip("[]").split(",") if x.strip()]
        names = {}
        for l in lines[i + 1:]:                       # names:\n  0: a\n  1: b   or   - a\n  - b
            t = l.strip()
            if not t or t.startswith("#"):
                continue
            if not l.startswith((" ", "\t")) and not t.startswith("- "):
                break  # next top-level key
            if t.startswith("- "):
                names[len(names)] = t[2:].strip().strip("'\"")
            elif ":" in t:
                k, v = t.split(":", 1)
                if k.strip().isdigit():
                    names[int(k.strip())] = v.strip().strip("'\"")
        return [names[k] for k in sorted(names)]
    return []


def find_data_yaml(images):
    for d in (images.parent, images.parent.parent, images):
        for name in ("data.yaml", "dataset.yaml", "data.yml"):
            f = d / name
            if f.is_file():
                return f
    return None


def dataset_preview(images_dir, labels_dir=None, classes_file=None):
    """What opening this folder would do, without creating anything."""
    images = Path(images_dir).expanduser() if images_dir else Path()
    exists = bool(images_dir) and images.is_dir()
    images = images.resolve() if exists else images
    labels = Path(labels_dir).expanduser() if labels_dir else images.parent / "labels"
    classes = Path(classes_file).expanduser() if classes_file else images.parent / "classes.txt"
    n_labels = 0
    if exists and labels.is_dir():
        stems = {f.stem for f in images.iterdir() if f.is_file() and f.suffix.lower() in IMG_EXT}
        n_labels = sum(1 for f in labels.glob("*.txt") if f.stem in stems)
    class_names = []
    if classes.is_file():
        class_names = [l.split("|")[0].strip() for l in classes.read_text(encoding="utf-8").splitlines() if l.strip()]
    yaml_file, yaml_names = (find_data_yaml(images) if exists else None), []
    if yaml_file:
        yaml_names = read_yaml_names(yaml_file)
    return {"exists": exists, "images_dir": str(images), "labels_dir": str(labels), "classes_file": str(classes),
            "image_count": _count_images(images) if exists else 0, "existing_labels": n_labels,
            "classes_exists": classes.is_file(), "class_names": class_names[:200],
            "yaml_file": str(yaml_file) if yaml_file else None, "yaml_names": yaml_names[:500]}


def load_recent():
    try:
        return json.loads(RECENT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_recent(images_dir, labels_dir, classes_file):
    item = {"images_dir": images_dir, "labels_dir": labels_dir, "classes_file": classes_file}
    items = [item] + [r for r in load_recent() if r.get("images_dir") != images_dir]
    try:
        RECENT_FILE.write_text(json.dumps(items[:8], indent=1), encoding="utf-8")
    except OSError:
        pass


def create_app(project=None):
    app = Flask(__name__)
    html = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")

    # The open dataset can change at runtime (start page), so routes look it up through P() / W().
    ctx = {"p": None, "w": None}

    def set_project(proj):
        ctx["p"], ctx["w"] = proj, (Worker(proj) if proj else None)
        app.worker = ctx["w"]

    def P():
        if ctx["p"] is None:
            raise NoProject()
        return ctx["p"]

    def W():
        P()
        return ctx["w"]

    set_project(project)

    @app.get("/")
    def index():
        return Response(html, mimetype="text/html")

    @app.get("/api/state")
    def state():
        if ctx["p"] is None:
            return jsonify({"project": None, "classes": [], "images": [], "worker": {"running": False, "done": 0,
                            "total": 0, "current": None, "message": "no dataset open"}})
        imgs = []
        for n in P().images():
            s = P().state.get(n, {})
            lp = P().label_path(n)
            count = 0
            if lp.exists():
                count = sum(1 for l in lp.read_text(encoding="utf-8").splitlines() if l.strip())
            imgs.append({"name": n, "status": P().status(n), "boxes": count, "note": s.get("note", ""),
                         "flag": bool(s.get("flag")), "flag_reason": s.get("flag_reason", ""),
                         "flag_note": s.get("flag_note", "")})
        return jsonify({
            "classes": P().classes(),
            "class_prompts": [e[1] for e in P().class_entries()],
            "class_descs": [e[2] for e in P().class_entries()],
            "images": imgs,
            "images_dir": str(P().images_dir),
            "labels_dir": str(P().labels_dir),
            "worker": {"running": W().running(), "done": W().done, "total": W().total,
                       "current": W().current, "message": W().message},
        })

    @app.get("/api/log")
    def log():
        return jsonify(W().log[-100:])

    @app.get("/api/image/<path:name>")
    def image(name):
        return send_file(P().image_path(name))

    @app.get("/api/thumb/<path:name>")
    def thumb(name):
        """Small cached preview for the image strip (full images would be slow to load by the hundred)."""
        src = P().image_path(name)
        tdir = P().tmp_dir / "thumbs"
        tdir.mkdir(exist_ok=True)
        dst = tdir / (src.stem + ".jpg")
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            with Image.open(src) as im:
                im = im.convert("RGB")
                im.thumbnail((240, 240))
                im.save(dst, quality=80)
        return send_file(dst, max_age=3600)

    @app.get("/api/labels/<path:name>")
    def get_labels(name):
        P().image_path(name)
        return jsonify(P().read_boxes(name))

    @app.post("/api/labels/<path:name>")
    def save_labels(name):
        P().image_path(name)
        body = request.get_json(force=True)
        P().write_boxes(name, body.get("boxes", []))
        P().set_status(name, body.get("status", "reviewed"))
        return jsonify({"ok": True})

    @app.post("/api/flag/<path:name>")
    def flag(name):
        P().image_path(name)
        body = request.get_json(force=True)
        P().set_flag(name, body.get("flag", False), body.get("reason", ""), body.get("note", ""))
        return jsonify({"ok": True})

    @app.post("/api/classes")
    def classes():
        body = request.get_json(force=True)
        if "update" in body or "rename" in body:
            idx = int(body.get("update", body.get("rename")))
            return jsonify(P().update_class(idx, body.get("name"), body.get("prompt"), body.get("description")))
        return jsonify(P().add_class(body.get("name", ""), body.get("prompt", ""), body.get("description", "")))

    @app.get("/api/backends")
    def backends():
        return jsonify(availability())

    @app.post("/api/run")
    def run():
        body = request.get_json(force=True)
        target = body.get("target", "unlabeled")
        if isinstance(target, list):
            names = target
        elif target == "all":
            names = P().images()
        elif target == "errors":
            names = [n for n in P().images() if P().status(n) == "error"]
        elif target == "auto":
            names = [n for n in P().images() if P().status(n) == "auto"]
        else:
            names = [n for n in P().images() if P().status(n) in ("none", "error")]
        relevant = {"claude": ("model",), "ollama": ("ollama_model", "ollama_url"), "gemini": ("gemini_model",),
                    "grounding_dino": ("gdino_model", "threshold"), "yolo_world": ("yolo_weights", "threshold")}
        keys = relevant.get(body.get("backend", "claude"), ("model",))
        opts = {k: body.get(k) for k in keys if body.get(k) not in (None, "")}
        ok = W().start(names, body.get("mode", "annotate"), body.get("backend", "claude"), opts,
                          bool(body.get("grid", False)), body.get("extra", "").strip())
        return jsonify({"ok": ok, "count": len(names)})

    @app.get("/api/health")
    def health():
        return jsonify(health_report(P(), int(request.args.get("low", 100))))

    @app.post("/api/stop")
    def stop():
        W().stop()
        return jsonify({"ok": True})

    @app.get("/api/export/yolo")
    def exp_yolo():
        only = request.args.get("reviewed") == "1"
        skip = request.args.get("skipflagged") == "1"
        val = float(request.args.get("val", 0.1))
        return send_file(export_yolo_zip(P(), val, only, skip_flagged=skip), mimetype="application/zip",
                         as_attachment=True, download_name="yolo_dataset.zip")

    @app.get("/api/export/coco")
    def exp_coco():
        only = request.args.get("reviewed") == "1"
        skip = request.args.get("skipflagged") == "1"
        data = json.dumps(export_coco(P(), only, skip), indent=1)
        return Response(data, mimetype="application/json",
                        headers={"Content-Disposition": "attachment; filename=annotations_coco.json"})


    # ---------------- start page: pick a dataset ----------------
    @app.get("/api/browse")
    def browse():
        return jsonify(browse_dir(request.args.get("path", "")))

    @app.post("/api/project/check")
    def project_check():
        body = request.get_json(force=True)
        return jsonify(dataset_preview(body.get("images_dir", ""), body.get("labels_dir"), body.get("classes_file")))

    @app.get("/api/project")
    def project_info():
        info = {"open": ctx["p"] is not None, "recent": load_recent()}
        if ctx["p"] is not None:
            pr = ctx["p"]
            info.update(images_dir=str(pr.images_dir), labels_dir=str(pr.labels_dir),
                        classes_file=str(pr.classes_file), image_count=len(pr.images()),
                        class_count=len(pr.classes()))
        return jsonify(info)

    @app.post("/api/project/open")
    def project_open():
        if ctx["w"] is not None and ctx["w"].running():
            return jsonify({"ok": False, "error": "A labeling job is running. Stop it first."}), 409
        body = request.get_json(force=True)
        pv = dataset_preview(body.get("images_dir", ""), body.get("labels_dir"), body.get("classes_file"))
        if not pv["exists"]:
            return jsonify({"ok": False, "error": "That images folder doesn't exist."}), 400
        # Optional: start the class list from the dataset's data.yaml (same IDs as the existing labels)
        if body.get("import_yaml") and pv["yaml_names"] and not pv["classes_exists"]:
            Path(pv["classes_file"]).parent.mkdir(parents=True, exist_ok=True)
            Path(pv["classes_file"]).write_text("\n".join(pv["yaml_names"]) + "\n", encoding="utf-8")
        proj = Project(pv["images_dir"], pv["labels_dir"], pv["classes_file"])
        set_project(proj)
        save_recent(pv["images_dir"], pv["labels_dir"], pv["classes_file"])
        print(f"Opened dataset: {proj.images_dir}  (labels: {proj.labels_dir}, classes: {proj.classes_file})", flush=True)
        return jsonify({"ok": True, **pv})

    @app.errorhandler(NoProject)
    def no_project(e):
        return jsonify({"error": "no_dataset", "message": "Open a dataset first."}), 409

    @app.errorhandler(FileNotFoundError)
    def not_found(e):
        return jsonify({"error": f"not found: {e}"}), 404

    return app


def load_dotenv(path):
    """Read KEY=value lines from a .env file into the environment (doesn't override real env vars)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v


def main():
    load_dotenv(Path(__file__).parent / ".env")
    ap = argparse.ArgumentParser(description="Claude-powered annotation dashboard")
    ap.add_argument("--images", help="Folder with images (optional: you can pick it on the start page)")
    ap.add_argument("--labels", help="Folder for YOLO .txt labels (default: <images>/../labels)")
    ap.add_argument("--classes", help="classes.txt (default: next to the images folder)")
    ap.add_argument("--port", type=int, default=5050)
    a = ap.parse_args()
    project = None
    if a.images:
        pv = dataset_preview(a.images, a.labels, a.classes)
        if not pv["exists"]:
            raise SystemExit(f"Images folder not found: {a.images}")
        project = Project(pv["images_dir"], pv["labels_dir"], pv["classes_file"])
        save_recent(pv["images_dir"], pv["labels_dir"], pv["classes_file"])
        print(f"Images:  {project.images_dir}\nLabels:  {project.labels_dir}\nClasses: {project.classes_file}")
    else:
        print("No dataset given: pick one on the start page in your browser.")
    app = create_app(project)
    print(f"Claude CLI: {find_claude()}")
    av = availability(check_cuda=False)  # skip the slow torch import so the server starts instantly
    print("Backends: claude=%s  gemini=%s  ollama=%s  grounding_dino=%s  yolo_world=%s" % (
        "yes" if av["claude"] else "no", "key found" if av["gemini_key"] else "no key",
        "running" if av["ollama"] is not None else "not running",
        "yes" if av["grounding_dino"] else "not installed", "yes" if av["yolo_world"] else "not installed"))
    print(f"Open http://127.0.0.1:{a.port}")
    app.run(host="127.0.0.1", port=a.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
