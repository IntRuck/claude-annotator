"""Readers for the files of an existing dataset (today's claude-annotator folders or any YOLO dataset).

classes.txt, data.yaml and YOLO label reading are moved from today's app.py (class_entries, read_yaml_names,
read_boxes) and keep their behaviour.
"""
import json
from dataclasses import dataclass
from pathlib import PurePosixPath

from annotator.image.thumbnails import IMAGE_EXTENSIONS

YAML_NAMES = {"data.yaml", "dataset.yaml", "data.yml", "dataset.yml"}
STATE_NAME = "_annot_state.json"
CLASSES_NAME = "classes.txt"
# Today's temp folder holds resized copies sent to the AI, not dataset images.
IGNORED_FOLDERS = {"_claude_tmp"}

# Today's statuses -> v2 statuses ("none" was today's word for unlabeled).
_STATUS = {"none": "unlabeled", "unlabeled": "unlabeled", "auto": "auto", "edited": "edited",
           "reviewed": "reviewed", "error": "error"}


@dataclass(frozen=True)
class StateEntry:
    status: str | None  # None = not given / unknown, keep what the import worked out
    note: str
    flagged: bool
    flag_reason: str
    flag_note: str


def classify(paths: list[str]) -> dict[str, str]:
    """What each uploaded file is: image, label, classes, yaml, state or ignored."""
    kinds = {}
    for raw in paths:
        p = PurePosixPath(raw.replace("\\", "/"))
        name = p.name.lower()
        if IGNORED_FOLDERS & set(p.parts[:-1]):
            kind = "ignored"
        elif p.suffix.lower() in IMAGE_EXTENSIONS:
            kind = "image"
        elif name == CLASSES_NAME:
            kind = "classes"
        elif name in YAML_NAMES:
            kind = "yaml"
        elif name == STATE_NAME:
            kind = "state"
        elif p.suffix.lower() == ".txt":
            kind = "label"
        else:
            kind = "ignored"
        kinds[raw] = kind
    return kinds


def parse_classes_txt(text: str) -> list[tuple[str, str, str]]:
    """`name | detector prompt | description` per line; only the name is required."""
    entries = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = [x.strip() for x in line.split("|", 2)] + ["", ""]
        entries.append((parts[0], parts[1], parts[2]))
    return entries


def parse_data_yaml_names(text: str) -> list[str]:
    """Class names from a YOLO data.yaml (list, `i: name` or `- name` form), without needing PyYAML."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.strip().startswith("names:"):
            continue
        rest = line.split(":", 1)[1].strip()
        if rest.startswith("["):
            return [x.strip().strip("'\"") for x in rest.strip("[]").split(",") if x.strip()]
        names = {}
        for raw in lines[i + 1:]:
            t = raw.strip()
            if not t or t.startswith("#"):
                continue
            if not raw.startswith((" ", "\t")) and not t.startswith("- "):
                break  # next top-level key
            if t.startswith("- "):
                names[len(names)] = t[2:].strip().strip("'\"")
            elif ":" in t:
                k, v = t.split(":", 1)
                if k.strip().isdigit():
                    names[int(k.strip())] = v.strip().strip("'\"")
        return [names[k] for k in sorted(names)]
    return []


def _yolo_line(parts: list[str]) -> dict:
    """Counting the numbers after the class: 4 = box `cx cy w h`; 5 = box with a 5th number (e.g. a confidence)
    ignored, as today; 6 or more and even = YOLO segmentation outline `x1 y1 x2 y2 ...`. Raises ValueError
    otherwise."""
    cls = int(float(parts[0]))
    numbers = [float(p) for p in parts[1:]]
    if cls < 0 or len(numbers) < 4 or (len(numbers) > 5 and len(numbers) % 2):
        raise ValueError
    if len(numbers) <= 5:
        cx, cy, w, h = numbers[:4]
        return {"cls": cls, "x1": cx - w / 2, "y1": cy - h / 2, "x2": cx + w / 2, "y2": cy + h / 2}
    xs, ys = numbers[::2], numbers[1::2]
    points = [[x, y] for x, y in zip(xs, ys, strict=True)]
    return {"cls": cls, "x1": min(xs), "y1": min(ys), "x2": max(xs), "y2": max(ys), "points": points}


def parse_yolo_label(text: str) -> tuple[list[dict], int]:
    """YOLO lines (`class cx cy w h`, or `class x1 y1 x2 y2 ...` outlines, all 0-1) -> corner boxes (outlines keep
    their dots in `points`), plus how many non-empty lines were unreadable."""
    boxes, bad = [], 0
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        try:
            boxes.append(_yolo_line(parts))
        except ValueError:
            bad += 1
    return boxes, bad


def parse_annot_state(text: str) -> dict[str, StateEntry]:
    """Today's _annot_state.json: per file name, its status, note and flag. Raises ValueError if not JSON."""
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("_annot_state.json should be an object keyed by file name")
    state = {}
    for name, entry in data.items():
        if not isinstance(entry, dict):
            continue
        flagged = bool(entry.get("flag"))
        state[name] = StateEntry(
            status=_STATUS.get(str(entry.get("status", "")).lower()),
            note=str(entry.get("note") or ""),
            flagged=flagged,
            flag_reason=str(entry.get("flag_reason") or "") if flagged else "",
            flag_note=str(entry.get("flag_note") or "") if flagged else "",
        )
    return state
