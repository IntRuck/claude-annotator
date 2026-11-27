"""Dataset health report, moved from today's app.health_report. Pure: works on rows already loaded.

Two changes from today:
- "Labelled" was "has a label file"; v2 uses `label.rules.is_labelled` (shared with exports).
- The "class ID not in class list" issue is gone: the database refuses a box whose class doesn't exist.
"""
from annotator.engine.geometry import iou
from annotator.label.rules import is_labelled

DUPLICATE_IOU = 0.85
TINY_SIDE = 0.005   # narrower or shorter than 0.5% of the image
CROWDED = 100       # more boxes than this on one image
SIZES = (("tiny", "tiny (<0.1%)", 0.001), ("small", "small (0.1-1%)", 0.01),
         ("medium", "medium (1-10%)", 0.1), ("large", "large (>10%)", float("inf")))
ISSUES = (
    ("flagged", "🚩 Flagged by you to check later"),
    ("unlabeled", "Unlabeled images"),
    ("errors", "AI errors"),
    ("empty", "Labeled but no boxes (background)"),
    ("duplicates", f"Possible duplicate boxes (same class, IoU > {DUPLICATE_IOU})"),
    ("tiny", f"Tiny boxes (< {TINY_SIDE * 100:g}% width or height)"),
    ("crowded", f"Very crowded (> {CROWDED} boxes)"),
    ("partly_outlined", "Partly outlined (some objects have no outline)"),  # only listed once outlines exist
)


def _size_key(area: float) -> str:
    return next(key for key, _, below in SIZES if area < below)


def _cell(a: float, b: float, grid: int) -> int:
    return min(grid - 1, max(0, int((a + b) / 2 * grid)))


def build_report(classes: list[tuple[int, str]], images: list, boxes: dict[int, list[dict]],
                 low_count: int = 100, grid: int = 20) -> dict:
    """`classes` are (index, name); `images` have id, status and flagged, in display order; `boxes` maps an image
    id to its boxes ({cls, x1, y1, x2, y2}, 0-1). Returns the report with snake_case keys (HealthReport)."""
    per_class = {index: {"index": index, "name": name, "boxes": 0, "image_ids": [], "area_sum": 0.0}
                 for index, name in classes}
    status_counts: dict[str, int] = {}
    sizes = {key: 0 for key, _, _ in SIZES}
    heat = [[0] * grid for _ in range(grid)]
    issues: dict[str, list[int]] = {key: [] for key, _ in ISSUES}
    total_boxes, labelled = 0, 0
    any_outlines = False

    for img in images:
        status_counts[img.status] = status_counts.get(img.status, 0) + 1
        if img.flagged:
            issues["flagged"].append(img.id)
        if img.status == "error":
            issues["errors"].append(img.id)
        image_boxes = boxes.get(img.id, [])
        if not is_labelled(img.status, len(image_boxes)):
            issues["unlabeled"].append(img.id)
            continue
        labelled += 1
        if not image_boxes:
            issues["empty"].append(img.id)
        if len(image_boxes) > CROWDED:
            issues["crowded"].append(img.id)
        outlined = sum(1 for b in image_boxes if b.get("points"))
        any_outlines = any_outlines or outlined > 0
        if 0 < outlined < len(image_boxes):
            issues["partly_outlined"].append(img.id)
        total_boxes += len(image_boxes)
        found = set()
        for i, b in enumerate(image_boxes):
            w, h = b["x2"] - b["x1"], b["y2"] - b["y1"]
            area = w * h
            pc = per_class.get(b["cls"])
            if pc is not None:
                pc["boxes"] += 1
                pc["area_sum"] += area
                if not pc["image_ids"] or pc["image_ids"][-1] != img.id:
                    pc["image_ids"].append(img.id)
            if w < TINY_SIDE or h < TINY_SIDE:
                found.add("tiny")
            sizes[_size_key(area)] += 1
            heat[_cell(b["y1"], b["y2"], grid)][_cell(b["x1"], b["x2"], grid)] += 1
            if any(b2["cls"] == b["cls"] and iou(b, b2) > DUPLICATE_IOU for b2 in image_boxes[i + 1:]):
                found.add("duplicates")
        for key in found:
            issues[key].append(img.id)

    with_data = [c["boxes"] for c in per_class.values() if c["boxes"] > 0]
    return {
        "summary": {
            "images": len(images), "labeled": labelled, "boxes": total_boxes,
            "avg_boxes_per_image": round(total_boxes / labelled, 1) if labelled else 0,
            "classes": len(classes), "classes_with_data": len(with_data),
            "imbalance_ratio": round(max(with_data) / min(with_data), 1) if with_data else 0,
            "status": status_counts,
        },
        "classes": [_class_row(c, low_count) for c in per_class.values()],
        "sizes": [{"key": key, "label": label, "count": sizes[key]} for key, label, _ in SIZES],
        "heatmap": heat,
        "issues": [{"key": key, "label": label, "count": len(issues[key]), "image_ids": issues[key]}
                   for key, label in ISSUES if key != "partly_outlined" or any_outlines],
        "low_count": low_count,
    }


def _class_row(c: dict, low_count: int) -> dict:
    if c["boxes"] == 0:
        warn = "no boxes"
    elif c["boxes"] < low_count:
        warn = f"low (< {low_count})"
    else:
        warn = ""
    return {
        "index": c["index"], "name": c["name"], "boxes": c["boxes"], "images": len(c["image_ids"]),
        "avg_area_pct": round(100 * c["area_sum"] / c["boxes"], 2) if c["boxes"] else 0,
        "warn": warn, "image_ids": c["image_ids"],
    }
