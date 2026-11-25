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


# ---------- refine overlay: the same copy with the current boxes drawn and numbered #0, #1, ... ----------
BOX = {"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5}


def test_the_overlay_is_the_same_size_as_the_clean_copy():
    original = encoded((3136, 1000))
    assert opened(prepare_for_vlm(original, boxes=[BOX])).size == opened(prepare_for_vlm(original)).size == (1568, 500)


def test_boxes_are_drawn_on_the_overlay_in_todays_pink():
    out = opened(prepare_for_vlm(encoded((400, 300), mode="RGB"), boxes=[BOX])).convert("RGB")
    r, g, b = out.getpixel((40, 150))          # left edge of the box (x1 = 0.1 of 400); JPEG softens the 2 px line
    assert r > 120 and r > g + 80 and r > b + 40


def test_without_boxes_nothing_is_drawn():
    plain = opened(prepare_for_vlm(encoded((400, 300)))).convert("RGB")
    assert plain.getpixel((40, 150)) == (0, 0, 0)


# ---------- the 0-1000 grid for Claude / Ollama (today's prep_image grid=True) ----------
def brightest(img: Image.Image, box) -> int:
    return max(sum(img.getpixel((x, y))) for x in range(box[0], box[2]) for y in range(box[1], box[3]))


def test_the_grid_draws_a_faint_line_every_tenth_of_the_image():
    out = opened(prepare_for_vlm(encoded((1000, 800)), grid=True)).convert("RGB")
    assert brightest(out, (99, 420, 102, 440)) > 60        # line at x = 100 (1/10 of 1000)
    assert brightest(out, (650, 559, 670, 562)) > 60       # line at y = 560 (7/10 of 800)
    assert brightest(out, (140, 420, 160, 440)) < 30       # between lines stays dark


def test_the_grid_numbers_its_lines_along_the_top_and_left_edges():
    out = opened(prepare_for_vlm(encoded((1000, 800)), grid=True)).convert("RGB")
    assert brightest(out, (502, 2, 530, 14)) > 250         # "500" at the top, right of the x = 500 line
    assert brightest(out, (2, 402, 30, 414)) > 250         # "500" on the left, under the y = 400 line


def test_no_grid_unless_asked():
    out = opened(prepare_for_vlm(encoded((1000, 800)))).convert("RGB")
    assert brightest(out, (99, 420, 102, 440)) == 0
