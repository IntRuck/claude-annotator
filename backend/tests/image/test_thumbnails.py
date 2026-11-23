import io

import pytest
from PIL import Image

from annotator.image.thumbnails import UnsupportedImageError, allowed_file_name, read_image


def png_bytes(size=(1000, 500), mode="RGB"):
    buf = io.BytesIO()
    Image.new(mode, size).save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.parametrize("name,ok", [
    ("a.jpg", True), ("b.JPEG", True), ("c.png", True), ("d.bmp", True), ("e.webp", True),
    ("notes.txt", False), ("noext", False), ("video.mp4", False),
])
def test_allowed_file_names_match_todays_image_types(name, ok):
    assert allowed_file_name(name) is ok


def test_read_image_gives_size_and_a_240px_jpeg_thumbnail():
    info = read_image(png_bytes((1000, 500)))
    assert (info.width, info.height) == (1000, 500)
    thumb = Image.open(io.BytesIO(info.thumbnail_jpeg))
    assert thumb.format == "JPEG"
    assert thumb.size == (240, 120)


def test_small_images_are_not_enlarged():
    info = read_image(png_bytes((100, 80)))
    assert Image.open(io.BytesIO(info.thumbnail_jpeg)).size == (100, 80)


def test_transparent_png_becomes_an_rgb_thumbnail():
    info = read_image(png_bytes((50, 50), mode="RGBA"))
    assert Image.open(io.BytesIO(info.thumbnail_jpeg)).mode == "RGB"


def test_bytes_that_are_not_an_image_are_refused():
    with pytest.raises(UnsupportedImageError):
        read_image(b"definitely not an image")
