"""The copy of a photo a VLM sees (moved from today's prep_image; the 0-1000 grid comes with the Claude/Ollama
engines). Originals in Storage are never changed.
"""
import io

from PIL import Image, ImageDraw, ImageFont

MAX_SIDE = 1568  # Claude's native max image side; bigger gets downscaled by the models anyway


def _font(size):
    for f in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            pass
    return ImageFont.load_default()


def prepare_for_vlm(data: bytes, boxes: list[dict] | None = None) -> bytes:
    """At most MAX_SIDE on the long side (shape kept), RGB JPEG at quality 92.
    With `boxes` (0-1 corners), each is drawn and numbered #0, #1, ... for refine (today's overlay)."""
    im = Image.open(io.BytesIO(data)).convert("RGB")
    scale = min(1.0, MAX_SIDE / max(im.size))
    if scale < 1.0:
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    if boxes:
        w, h = im.size
        draw = ImageDraw.Draw(im, "RGBA")
        f = _font(max(12, w // 60))
        for i, b in enumerate(boxes):
            x1, y1, x2, y2 = b["x1"] * w, b["y1"] * h, b["x2"] * w, b["y2"] * h
            draw.rectangle([x1, y1, x2, y2], outline=(255, 0, 80, 255), width=max(2, w // 400))
            draw.text((x1 + 3, y1 + 2), f"#{i}", fill=(255, 255, 0, 255), font=f,
                      stroke_width=2, stroke_fill=(0, 0, 0, 255))
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=92)
    return out.getvalue()
