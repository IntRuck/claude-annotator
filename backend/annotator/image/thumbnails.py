"""Reading uploaded images: check they open, get their size, and make the 240 px strip thumbnail."""
import io
from dataclasses import dataclass
from pathlib import PurePath

from PIL import Image, UnidentifiedImageError

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")  # same types as today's app, in display order
THUMB_SIDE = 240


class UnsupportedImageError(Exception):
    pass


@dataclass(frozen=True)
class ImageInfo:
    width: int
    height: int
    thumbnail_jpeg: bytes


def allowed_file_name(name: str) -> bool:
    return PurePath(name).suffix.lower() in IMAGE_EXTENSIONS


def read_image(data: bytes) -> ImageInfo:
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            width, height = im.size
            thumb = im.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as e:
        raise UnsupportedImageError(str(e)) from e
    thumb.thumbnail((THUMB_SIDE, THUMB_SIDE))
    out = io.BytesIO()
    thumb.save(out, format="JPEG", quality=80)
    return ImageInfo(width, height, out.getvalue())
