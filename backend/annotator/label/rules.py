"""Box save rules, moved from today's Project.write_boxes, plus the outline rules (V9 `points`)."""
import math

MIN_SIDE = 0.001  # a box this thin or thinner (as a fraction of the image) is dropped
LABELLED_STATUSES = ("auto", "edited", "reviewed")
MAX_DOTS = 1000          # an outline keeps at most this many dots (the V9 check allows 3-1000)
MIN_OUTLINE_AREA = 1e-9  # an outline enclosing less (dots on one line) is no outline


def _clamp01(v) -> float:
    return max(0.0, min(1.0, float(v)))


def outline_area(points) -> float:
    """Area inside the outline (shoelace formula), in image fractions, whichever way round the dots go."""
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points, [*points[1:], points[0]], strict=True):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2


def outline_bounds(points) -> tuple[float, float, float, float]:
    """The smallest box around the dots: (x1, y1, x2, y2)."""
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def clean_points(points) -> list[list[float]] | None:
    """Clamp each dot into the image (6 decimals), drop a dot equal to the one before it and a last dot equal to
    the first, and keep every k-th dot when there are more than MAX_DOTS. None when fewer than 3 dots are left or
    they enclose no area."""
    dots: list[list[float]] = []
    for x, y in points:
        dot = [round(_clamp01(x), 6), round(_clamp01(y), 6)]
        if not dots or dot != dots[-1]:
            dots.append(dot)
    if len(dots) > 1 and dots[-1] == dots[0]:
        dots.pop()
    if len(dots) > MAX_DOTS:
        dots = dots[::math.ceil(len(dots) / MAX_DOTS)]
    if len(dots) < 3 or outline_area(dots) < MIN_OUTLINE_AREA:
        return None
    return dots


def _with_outline(b: dict) -> dict:
    """An outlined box's corners become the box around its cleaned dots; an unusable outline is dropped (the box
    stays as sent). Boxes without a `points` key come back unchanged."""
    if b.get("points") is None:
        return b
    dots = clean_points(b["points"])
    if dots is None:
        return {**b, "points": None}
    x1, y1, x2, y2 = outline_bounds(dots)
    return {**b, "points": dots, "x1": x1, "y1": y1, "x2": x2, "y2": y2}


def clean_boxes(boxes: list[dict]) -> list[dict]:
    """Outlines first (see _with_outline), then: clamp corners into the image, put them in order, and drop boxes
    with a side <= MIN_SIDE. Other fields (cls, conf, ...) are kept as they are."""
    cleaned = []
    for b in map(_with_outline, boxes):
        x1, x2 = sorted((_clamp01(b["x1"]), _clamp01(b["x2"])))
        y1, y2 = sorted((_clamp01(b["y1"]), _clamp01(b["y2"])))
        if x2 - x1 <= MIN_SIDE or y2 - y1 <= MIN_SIDE:
            continue
        cleaned.append({**b, "x1": x1, "y1": y1, "x2": x2, "y2": y2})
    return cleaned


def is_labelled(status: str, box_count: int) -> bool:
    """Today "labelled" meant "has a label file". In v2: the AI, an import or a person saved boxes for it
    (status auto / edited / reviewed), or it has boxes whatever its status. Used by the health check and exports."""
    return status in LABELLED_STATUSES or box_count > 0
