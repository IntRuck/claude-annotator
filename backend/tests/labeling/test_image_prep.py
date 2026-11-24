"""The copy a VLM sees: at most 1568 px on the long side, JPEG (moved from today's prep_image, minus grid/overlay)."""
import io

from PIL import Image

from annotator.labeling.image_prep import MAX_SIDE, prepare_for_vlm


def encoded(size, mode="RGB", fmt="JPEG") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size).save(buf, format=fmt)
    return buf.getvalue()


def opened(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def test_a_big_photo_is_shrunk_to_1568_on_the_long_side_keeping_its_shape():
    out = opened(prepare_for_vlm(encoded((4000, 3000))))
    assert MAX_SIDE == 1568
    assert out.size == (1568, 1176)
    assert out.format == "JPEG"


def test_a_small_photo_keeps_its_size():
    assert opened(prepare_for_vlm(encoded((640, 480)))).size == (640, 480)


def test_png_with_transparency_becomes_an_rgb_jpeg():
    out = opened(prepare_for_vlm(encoded((50, 40), mode="RGBA", fmt="PNG")))
    assert (out.format, out.mode, out.size) == ("JPEG", "RGB", (50, 40))
