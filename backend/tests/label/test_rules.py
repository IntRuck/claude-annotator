"""Box save rules: same as today's write_boxes (the old app's tests)."""
import pytest

from annotator.label.rules import clean_boxes


def test_clamps_sorts_corners_and_drops_tiny_boxes_like_today():
    cleaned = clean_boxes([
        {"cls": 1, "x1": 0.6, "y1": 0.8, "x2": 0.2, "y2": 0.4},      # reversed corners
        {"cls": 0, "x1": -0.5, "y1": 0.5, "x2": 0.5, "y2": 1.5},     # outside the image
        {"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.1005, "y2": 0.5},   # too thin: dropped
    ])
    assert cleaned == [
        pytest.approx({"cls": 1, "x1": 0.2, "y1": 0.4, "x2": 0.6, "y2": 0.8}),
        pytest.approx({"cls": 0, "x1": 0.0, "y1": 0.5, "x2": 0.5, "y2": 1.0}),
    ]


def test_box_exactly_0_001_wide_is_dropped_like_today():
    # 0.0 -> 0.001 is exactly 0.001 in floating point (0.5 -> 0.501 is a hair more, and is kept, as today).
    assert clean_boxes([{"cls": 0, "x1": 0.0, "y1": 0.1, "x2": 0.001, "y2": 0.5}]) == []
    assert len(clean_boxes([{"cls": 0, "x1": 0.5, "y1": 0.1, "x2": 0.501, "y2": 0.5}])) == 1


def test_extra_fields_like_confidence_are_kept():
    assert clean_boxes([{"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5, "conf": 0.9}])[0]["conf"] == 0.9


def test_an_image_is_labelled_once_saved_by_the_ai_an_import_or_a_person_or_when_it_has_boxes():
    from annotator.label.rules import is_labelled
    assert [is_labelled(s, 0) for s in ("auto", "edited", "reviewed")] == [True, True, True]
    assert [is_labelled(s, 0) for s in ("unlabeled", "error")] == [False, False]
    assert is_labelled("unlabeled", 2) and is_labelled("error", 1)


# ---------- outlines ----------
def test_an_outline_sets_the_box_to_the_smallest_box_around_its_dots():
    [b] = clean_boxes([{"cls": 0, "x1": 0, "y1": 0, "x2": 1, "y2": 1,
                        "points": [[0.2, 0.1], [0.6, 0.3], [0.3, 0.7]]}])
    assert (b["x1"], b["y1"], b["x2"], b["y2"]) == pytest.approx((0.2, 0.1, 0.6, 0.7))
    assert b["points"] == [[0.2, 0.1], [0.6, 0.3], [0.3, 0.7]]


def test_outline_dots_are_clamped_and_repeats_dropped():
    from annotator.label.rules import clean_points
    assert clean_points([[1.0000001, 0.5], [1.0000001, 0.5], [0.5, -0.2], [0.2, 0.5], [1.0, 0.5]]) == [
        [1.0, 0.5], [0.5, 0.0], [0.2, 0.5]]


@pytest.mark.parametrize("points", [
    [[0.2, 0.2], [0.4, 0.4]],                 # only 2 dots
    [[0.1, 0.1], [0.2, 0.2], [0.3, 0.3]],     # 3 dots in a straight line: no area
])
def test_an_outline_under_3_dots_or_with_no_area_becomes_a_plain_box(points):
    [b] = clean_boxes([{"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5, "points": points}])
    assert b["points"] is None
    assert (b["x1"], b["y1"], b["x2"], b["y2"]) == pytest.approx((0.1, 0.1, 0.5, 0.5))


def test_an_outline_over_1000_dots_is_thinned_evenly():
    import math

    from annotator.label.rules import MAX_DOTS, clean_points
    circle = [[0.5 + 0.4 * math.cos(2 * math.pi * i / 2500), 0.5 + 0.4 * math.sin(2 * math.pi * i / 2500)]
              for i in range(2500)]
    kept = clean_points(circle)
    assert 3 <= len(kept) <= MAX_DOTS == 1000
    assert kept[0] == [0.9, 0.5]


def test_outline_area_is_the_shoelace_area():
    from annotator.label.rules import outline_area
    square = [[0, 0], [1, 0], [1, 1], [0, 1]]
    assert outline_area(square) == pytest.approx(1.0)
    assert outline_area(square[::-1]) == pytest.approx(1.0)


def test_boxes_without_points_are_unchanged():
    assert clean_boxes([{"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5}]) == [
        {"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5}]
