"""Box save rules, moved from today's Project.write_boxes."""

MIN_SIDE = 0.001  # a box this thin or thinner (as a fraction of the image) is dropped


def _clamp01(v) -> float:
    return max(0.0, min(1.0, float(v)))


def clean_boxes(boxes: list[dict]) -> list[dict]:
    """Clamp corners into the image, put them in order, and drop boxes with a side <= MIN_SIDE.
    Other fields (cls, conf, ...) are kept as they are."""
    cleaned = []
    for b in boxes:
        x1, x2 = sorted((_clamp01(b["x1"]), _clamp01(b["x2"])))
        y1, y2 = sorted((_clamp01(b["y1"]), _clamp01(b["y2"])))
        if x2 - x1 <= MIN_SIDE or y2 - y1 <= MIN_SIDE:
            continue
        cleaned.append({**b, "x1": x1, "y1": y1, "x2": x2, "y2": y2})
    return cleaned
