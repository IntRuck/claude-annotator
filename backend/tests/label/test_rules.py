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
