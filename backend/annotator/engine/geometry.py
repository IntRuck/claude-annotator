"""Box helpers shared by the engines (moved unchanged from backends.py)."""


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
