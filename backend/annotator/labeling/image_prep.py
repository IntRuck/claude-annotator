"""The copy of a photo a VLM sees (moved from today's prep_image; the grid and refine overlay come later).

Originals in Storage are never changed.
"""
import io

from PIL import Image

MAX_SIDE = 1568  # Claude's native max image side; bigger gets downscaled by the models anyway


def prepare_for_vlm(data: bytes) -> bytes:
    """At most MAX_SIDE on the long side (shape kept), RGB JPEG at quality 92."""
    im = Image.open(io.BytesIO(data)).convert("RGB")
    scale = min(1.0, MAX_SIDE / max(im.size))
    if scale < 1.0:
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=92)
    return out.getvalue()
