"""Prompts and reply parsing for the VLM engines (moved from backends.py; only the bare-list fix is new)."""
import json
import re

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
    # The outermost JSON object, or a bare list (whichever starts first).
    m = re.search(r"\{.*\}|\[.*\]", text, re.S)
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
