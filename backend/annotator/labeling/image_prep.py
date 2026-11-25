"""The copy of a photo a VLM sees (moved from today's prep_image). Originals in Storage are never changed."""
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


def prepare_for_vlm(data: bytes, boxes: list[dict] | None = None, grid: bool = False) -> bytes:
    """At most MAX_SIDE on the long side (shape kept), RGB JPEG at quality 92.
    `grid` draws a faint line every 100 units of the 0-1000 scale, numbered on the top and left edges (Claude/Ollama
    can read coordinates off it). With `boxes` (0-1 corners), each is drawn and numbered #0, #1, ... for refine."""
    im = Image.open(io.BytesIO(data)).convert("RGB")
    scale = min(1.0, MAX_SIDE / max(im.size))
    if scale < 1.0:
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    w, h = im.size
    draw = ImageDraw.Draw(im, "RGBA")
    if grid:
        f = _font(max(10, w // 90))
        for i in range(1, 10):
            x, y = w * i / 10, h * i / 10
            draw.line([(x, 0), (x, h)], fill=(255, 255, 255, 70), width=1)
            draw.line([(0, y), (w, y)], fill=(255, 255, 255, 70), width=1)
            draw.text((x + 2, 2), str(i * 100), fill=(255, 255, 0, 200), font=f)
            draw.text((2, y + 2), str(i * 100), fill=(255, 255, 0, 200), font=f)
    if boxes:
        f = _font(max(12, w // 60))
        for i, b in enumerate(boxes):
            x1, y1, x2, y2 = b["x1"] * w, b["y1"] * h, b["x2"] * w, b["y2"] * h
            draw.rectangle([x1, y1, x2, y2], outline=(255, 0, 80, 255), width=max(2, w // 400))
            draw.text((x1 + 3, y1 + 2), f"#{i}", fill=(255, 255, 0, 255), font=f,
                      stroke_width=2, stroke_fill=(0, 0, 0, 255))
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=92)
    return out.getvalue()
