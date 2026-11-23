"""
Claude Annotator: local dashboard that uses Claude Code (signed in with your
Claude plan) to auto-annotate an image folder for object detection, with a
built-in box editor for manual fixes.

Run:
    python app.py --images path/to/images --classes classes.txt

Labels are written as YOLO .txt files (class cx cy w h, normalized 0-1).
"""
import argparse
import io
import json
import os
import random
import re
import shutil
import subprocess
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file
from PIL import Image, ImageDraw, ImageFont

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
    def classes(self):
        lines = self.classes_file.read_text(encoding="utf-8").splitlines()
        return [l.strip() for l in lines if l.strip()]

    def add_class(self, name):
        name = name.strip()
        with self.lock:
            cls = self.classes()
            if name and name not in cls:
                cls.append(name)  # always append so existing IDs never shift
                self.classes_file.write_text("\n".join(cls) + "\n", encoding="utf-8")
            return self.classes()

    def rename_class(self, idx, name):
        with self.lock:
            cls = self.classes()
            if 0 <= idx < len(cls) and name.strip():
                cls[idx] = name.strip()
                self.classes_file.write_text("\n".join(cls) + "\n", encoding="utf-8")
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

    # state -----------------------------------------------------------------
    def set_status(self, name, status, note=""):
        with self.lock:
            self.state[name] = {"status": status, "note": note,
                                "updated": datetime.now().isoformat(timespec="seconds")}
            self.state_file.write_text(json.dumps(self.state, indent=1), encoding="utf-8")

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
# Prompts
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


def class_block(classes):
    return "\n".join(f"- {c}" for c in classes)


def annotate_prompt(img_file, classes, extra, grid):
    g = ("\nThe image has a faint grid every 100 units with labels on the top and left edges. "
         "Use it to read coordinates accurately; the grid is not an object.") if grid else ""
    return f"""Use the Read tool to open the image file: {img_file}

You are labeling this image for an object detection training dataset.{g}

Classes (use these exact names):
{class_block(classes)}

{RULES}
{('Extra instructions: ' + extra) if extra else ''}

{OUTPUT}"""


def refine_prompt(clean_file, overlay_file, classes, current, extra):
    return f"""Use the Read tool to open two images:
1. {clean_file}  (the original image)
2. {overlay_file}  (the same image with the current boxes drawn and numbered #0, #1, ...)

You are reviewing labels for an object detection training dataset.

Classes (use these exact names):
{class_block(classes)}

Current boxes (0-1000 scale, index matches the # on the overlay):
{json.dumps(current)}

Fix every problem you can see: loose or cut-off boxes, one object split into several boxes,
duplicate boxes on the same object, wrong class names, and missing objects. Keep correct boxes as they are.

{RULES}
{('Extra instructions: ' + extra) if extra else ''}

Return the complete corrected list (not just the changes).
{OUTPUT}"""


# --------------------------------------------------------------------------
# Claude Code CLI
# --------------------------------------------------------------------------
class LimitReached(Exception):
    pass


LIMIT_PAT = re.compile(r"(usage limit|limit reached|5-hour limit|weekly limit|rate limit)", re.I)


def find_claude():
    return os.environ.get("CLAUDE_BIN") or shutil.which("claude") or shutil.which("claude.cmd") or "claude"


def call_claude(prompt, workdir, model, timeout=300):
    cmd = [find_claude(), "-p", prompt,
           "--output-format", "json",
           "--allowedTools", "Read",
           "--max-turns", "6",
           "--add-dir", str(workdir)]
    if model:
        cmd += ["--model", model]
    env = dict(os.environ)
    # Make sure the CLI uses your Claude plan login, not a paid API key.
    env.pop("ANTHROPIC_API_KEY", None)
    proc = subprocess.run(cmd, cwd=str(workdir), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, env=env)
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    text = out
    is_error = proc.returncode != 0
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


def parse_objects(text, classes, W=1000, H=1000):
    """Extract {"objects": [...]} from Claude's reply into normalized boxes."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("No JSON in reply: " + text[:200])
    data = json.loads(m.group(0))
    objs = data.get("objects", data if isinstance(data, list) else [])
    lower = {c.lower(): i for i, c in enumerate(classes)}
    boxes, unknown = [], set()
    for o in objs:
        name = str(o.get("class", "")).strip()
        idx = lower.get(name.lower())
        if idx is None:
            unknown.add(name)
            continue
        x1, y1, x2, y2 = [float(v) for v in o["box"][:4]]
        boxes.append({"cls": idx, "x1": x1 / 1000, "y1": y1 / 1000, "x2": x2 / 1000, "y2": y2 / 1000})
    return boxes, unknown


def to_1000(boxes, classes):
    return [{"class": classes[b["cls"]] if b["cls"] < len(classes) else str(b["cls"]),
             "box": [round(b["x1"] * 1000), round(b["y1"] * 1000),
                     round(b["x2"] * 1000), round(b["y2"] * 1000)]} for b in boxes]


# --------------------------------------------------------------------------
# Background worker
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

    def start(self, names, mode, model, grid, extra):
        if self.running():
            return False
        self.stop_flag.clear()
        self.queue = list(names)
        self.done, self.total = 0, len(self.queue)
        self.thread = threading.Thread(target=self._run, args=(mode, model, grid, extra), daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.stop_flag.set()

    def _run(self, mode, model, grid, extra):
        classes = self.p.classes()
        if not classes:
            self.message = "No classes defined"
            self._log(self.message)
            return
        self._log(f"Start {mode} on {self.total} image(s), model={model or 'default'}, grid={grid}")
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
                    n, unknown = self._refine_one(name, classes, model, extra)
                else:
                    n, unknown = self._annotate_one(name, classes, model, grid, extra)
                note = f"unknown classes ignored: {', '.join(sorted(unknown))}" if unknown else ""
                self.p.set_status(name, "auto", note)
                self._log(f"{name}: {n} box(es) in {time.time() - t0:.0f}s {note}")
            except LimitReached as e:
                self.message = "Claude usage limit reached. Paused; resume after reset."
                self._log(f"LIMIT: {e}")
                break
            except Exception as e:
                self.p.set_status(name, "error", str(e)[:300])
                self._log(f"{name}: ERROR {e}")
            self.done += 1
        else:
            self.message = "finished"
        self.current = None
        self._log(f"Done {self.done}/{self.total}")

    def _annotate_one(self, name, classes, model, grid, extra):
        src = self.p.image_path(name)
        tmp = self.p.tmp_dir / (Path(name).stem + "__in.jpg")
        prep_image(src, tmp, grid=grid)
        text = call_claude(annotate_prompt(tmp.name, classes, extra, grid), self.p.tmp_dir, model)
        boxes, unknown = parse_objects(text, classes)
        self.p.write_boxes(name, boxes)
        return len(boxes), unknown

    def _refine_one(self, name, classes, model, extra):
        src = self.p.image_path(name)
        current = self.p.read_boxes(name)
        clean = self.p.tmp_dir / (Path(name).stem + "__clean.jpg")
        over = self.p.tmp_dir / (Path(name).stem + "__overlay.jpg")
        prep_image(src, clean)
        prep_image(src, over, boxes=current, classes=classes)
        text = call_claude(refine_prompt(clean.name, over.name, classes, to_1000(current, classes), extra),
                           self.p.tmp_dir, model)
        boxes, unknown = parse_objects(text, classes)
        self.p.write_boxes(name, boxes)
        return len(boxes), unknown


# --------------------------------------------------------------------------
# Dataset health check
# --------------------------------------------------------------------------
def iou(a, b):
    ix = max(0.0, min(a["x2"], b["x2"]) - max(a["x1"], b["x1"]))
    iy = max(0.0, min(a["y2"], b["y2"]) - max(a["y1"], b["y1"]))
    inter = ix * iy
    ua = (a["x2"] - a["x1"]) * (a["y2"] - a["y1"]) + (b["x2"] - b["x1"]) * (b["y2"] - b["y1"]) - inter
    return inter / ua if ua > 0 else 0.0


def health_report(p, low_count=100, grid=20):
    classes = p.classes()
    nC = len(classes)
    per_class = [{"id": i, "name": c, "boxes": 0, "images": [], "area_sum": 0.0} for i, c in enumerate(classes)]
    status_counts = {}
    size_buckets = {"tiny (<0.1%)": 0, "small (0.1-1%)": 0, "medium (1-10%)": 0, "large (>10%)": 0}
    heat = [[0] * grid for _ in range(grid)]
    issues = {
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
def export_yolo_zip(p, val_ratio=0.1, only_reviewed=False, seed=0):
    classes = p.classes()
    names = [n for n in p.images() if p.label_path(n).exists()]
    if only_reviewed:
        names = [n for n in names if p.status(n) == "reviewed"]
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


def export_coco(p, only_reviewed=False):
    classes = p.classes()
    coco = {"images": [], "annotations": [],
            "categories": [{"id": i, "name": c} for i, c in enumerate(classes)]}
    ann_id = 1
    for img_id, n in enumerate(p.images(), start=1):
        if not p.label_path(n).exists():
            continue
        if only_reviewed and p.status(n) != "reviewed":
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
def create_app(project):
    app = Flask(__name__)
    worker = Worker(project)
    html = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")

    @app.get("/")
    def index():
        return Response(html, mimetype="text/html")

    @app.get("/api/state")
    def state():
        imgs = []
        for n in project.images():
            s = project.state.get(n, {})
            lp = project.label_path(n)
            count = 0
            if lp.exists():
                count = sum(1 for l in lp.read_text(encoding="utf-8").splitlines() if l.strip())
            imgs.append({"name": n, "status": project.status(n), "boxes": count, "note": s.get("note", "")})
        return jsonify({
            "classes": project.classes(),
            "images": imgs,
            "images_dir": str(project.images_dir),
            "labels_dir": str(project.labels_dir),
            "worker": {"running": worker.running(), "done": worker.done, "total": worker.total,
                       "current": worker.current, "message": worker.message},
        })

    @app.get("/api/log")
    def log():
        return jsonify(worker.log[-100:])

    @app.get("/api/image/<path:name>")
    def image(name):
        return send_file(project.image_path(name))

    @app.get("/api/labels/<path:name>")
    def get_labels(name):
        project.image_path(name)
        return jsonify(project.read_boxes(name))

    @app.post("/api/labels/<path:name>")
    def save_labels(name):
        project.image_path(name)
        body = request.get_json(force=True)
        project.write_boxes(name, body.get("boxes", []))
        project.set_status(name, body.get("status", "reviewed"))
        return jsonify({"ok": True})

    @app.post("/api/classes")
    def classes():
        body = request.get_json(force=True)
        if "rename" in body:
            return jsonify(project.rename_class(int(body["rename"]), body.get("name", "")))
        return jsonify(project.add_class(body.get("name", "")))

    @app.post("/api/run")
    def run():
        body = request.get_json(force=True)
        target = body.get("target", "unlabeled")
        if isinstance(target, list):
            names = target
        elif target == "all":
            names = project.images()
        elif target == "errors":
            names = [n for n in project.images() if project.status(n) == "error"]
        elif target == "auto":
            names = [n for n in project.images() if project.status(n) == "auto"]
        else:
            names = [n for n in project.images() if project.status(n) in ("none", "error")]
        ok = worker.start(names, body.get("mode", "annotate"), body.get("model", "sonnet"),
                          bool(body.get("grid", False)), body.get("extra", "").strip())
        return jsonify({"ok": ok, "count": len(names)})

    @app.get("/api/health")
    def health():
        return jsonify(health_report(project, int(request.args.get("low", 100))))

    @app.post("/api/stop")
    def stop():
        worker.stop()
        return jsonify({"ok": True})

    @app.get("/api/export/yolo")
    def exp_yolo():
        only = request.args.get("reviewed") == "1"
        val = float(request.args.get("val", 0.1))
        return send_file(export_yolo_zip(project, val, only), mimetype="application/zip",
                         as_attachment=True, download_name="yolo_dataset.zip")

    @app.get("/api/export/coco")
    def exp_coco():
        only = request.args.get("reviewed") == "1"
        data = json.dumps(export_coco(project, only), indent=1)
        return Response(data, mimetype="application/json",
                        headers={"Content-Disposition": "attachment; filename=annotations_coco.json"})

    @app.errorhandler(FileNotFoundError)
    def not_found(e):
        return jsonify({"error": f"not found: {e}"}), 404

    app.worker = worker
    return app


def main():
    ap = argparse.ArgumentParser(description="Claude-powered annotation dashboard")
    ap.add_argument("--images", required=True, help="Folder with images")
    ap.add_argument("--labels", help="Folder for YOLO .txt labels (default: <images>/../labels)")
    ap.add_argument("--classes", default="classes.txt", help="Text file, one class name per line")
    ap.add_argument("--port", type=int, default=5050)
    a = ap.parse_args()
    images = Path(a.images)
    labels = Path(a.labels) if a.labels else images.parent / "labels"
    project = Project(images, labels, a.classes)
    app = create_app(project)
    print(f"Images:  {project.images_dir}\nLabels:  {project.labels_dir}\nClasses: {project.classes_file}")
    print(f"Claude CLI: {find_claude()}")
    print(f"Open http://127.0.0.1:{a.port}")
    app.run(host="127.0.0.1", port=a.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
