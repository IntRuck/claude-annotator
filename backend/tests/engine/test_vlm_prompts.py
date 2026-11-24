"""Moved from backends.py: geometry, VLM prompts, reply parsing. Same cases as tests/legacy/test_vlm_shared.py."""
import json

import pytest

from annotator.engine import geometry as g
from annotator.engine import vlm_prompts as b
from annotator.engine.gemini import client as gemini


# ---------- geometry ----------
def box(x1, y1, x2, y2, cls=0, **kw):
    return {"cls": cls, "x1": x1, "y1": y1, "x2": x2, "y2": y2, **kw}


def test_iou_identical_disjoint_and_partial():
    assert g.iou(box(0, 0, 1, 1), box(0, 0, 1, 1)) == 1.0
    assert g.iou(box(0, 0, 0.1, 0.1), box(0.5, 0.5, 0.6, 0.6)) == 0.0
    assert g.iou(box(0, 0, 0.2, 0.2), box(0.1, 0, 0.3, 0.2)) == pytest.approx(1 / 3)


def test_nms_drops_lower_confidence_same_class_overlap_but_keeps_other_classes():
    kept = g.nms([
        box(0, 0, 1, 1, cls=0, conf=0.5),
        box(0, 0, 1, 1, cls=0, conf=0.9),
        box(0, 0, 1, 1, cls=1, conf=0.4),
    ])
    assert [(k["cls"], k["conf"]) for k in kept] == [(0, 0.9), (1, 0.4)]


def test_nms_keeps_same_class_boxes_that_overlap_less_than_threshold():
    kept = g.nms([box(0, 0, 0.2, 0.2), box(0.15, 0, 0.35, 0.2)], thr=0.6)
    assert len(kept) == 2


def test_to_1000_uses_class_names_and_rounds_coordinates():
    out = g.to_1000([box(0.1234, 0.5, 0.9876, 1.0, cls=1), box(0, 0, 0.5, 0.5, cls=7)], ["can", "bottle"])
    assert out == [
        {"class": "bottle", "box": [123, 500, 988, 1000]},
        {"class": "7", "box": [0, 0, 500, 500]},
    ]


# ---------- prompts ----------
def test_class_block_prefers_description_then_differing_prompt_then_plain_name():
    block = b.class_block(
        ["sardine_155g", "spray_bottle", "cream_bottle"],
        ["red tin can", "blue spray bottle", "cream bottle"],
        ["Short round red tin", "", ""],
    )
    assert block.splitlines() == [
        "- sardine_155g: Short round red tin",
        "- spray_bottle  (looks like: blue spray bottle)",
        "- cream_bottle",
    ]


def test_annotate_prompt_mentions_grid_and_extra_instructions_only_when_given():
    with_all = b.annotate_prompt("REF\n", ["can"], ["can"], "Ignore the top shelf", True)
    plain = b.annotate_prompt("REF\n", ["can"], ["can"], "", False)

    assert with_all.startswith("REF\n")
    assert "faint grid every 100 units" in with_all
    assert "Extra instructions: Ignore the top shelf" in with_all
    assert "grid" not in plain
    assert "Extra instructions" not in plain
    for text in (with_all, plain):
        assert b.RULES in text
        assert b.OUTPUT in text
        assert "- can" in text


def test_refine_prompt_includes_current_boxes_and_asks_for_the_full_list():
    current = [{"class": "can", "box": [1, 2, 3, 4]}]
    text = b.refine_prompt("", ["can"], ["can"], current, "", None)
    assert json.dumps(current) in text
    assert "numbered #0, #1" in text
    assert "Return the complete corrected list (not just the changes)." in text


def test_gemini_rules_ask_for_y_first_box_2d():
    assert "box_2d is [ymin, xmin, ymax, xmax]" in gemini.GEMINI_RULES
    assert "[x1, y1, x2, y2]" not in gemini.GEMINI_RULES
    assert '"box_2d": [ymin, xmin, ymax, xmax]' in gemini.GEMINI_OUTPUT


# ---------- parse_objects ----------
def test_parse_objects_reads_json_inside_text_and_scales_0_1000():
    text = 'Sure! {"objects": [{"class": "CAN", "box": [100, 200, 300, 400]}]} done'
    boxes, unknown = b.parse_objects(text, ["can", "bottle"])
    assert boxes == [box(0.1, 0.2, 0.3, 0.4)]
    assert unknown == set()


def test_parse_objects_collects_unknown_class_names_and_accepts_other_box_keys():
    text = json.dumps({"objects": [
        {"label": "bottle", "bbox_2d": [0, 0, 500, 500]},
        {"class": "pear", "box": [0, 0, 1, 1]},
        {"class": "can", "bbox": [0, 0, 1000, 1000, 99]},
    ]})
    boxes, unknown = b.parse_objects(text, ["can", "bottle"])
    assert boxes == [box(0, 0, 0.5, 0.5, cls=1), box(0, 0, 1, 1, cls=0)]
    assert unknown == {"pear"}


def test_parse_objects_reads_a_bare_list_reply():
    # Today's regex grabbed the inner object of a bare list and found nothing; a model that answers with a
    # plain list now gets its boxes (same rule as Gemini's parser).
    boxes, unknown = b.parse_objects('[{"class": "can", "box": [0, 0, 1000, 1000]}]', ["can"])
    assert boxes == [box(0, 0, 1, 1)]
    assert unknown == set()


def test_parse_objects_without_json_raises():
    with pytest.raises(ValueError, match="No JSON in reply"):
        b.parse_objects("I can't see anything", ["can"])


def test_parse_objects_uses_pixel_scale_when_size_given_and_values_exceed_1000():
    text = '{"objects": [{"class": "can", "box": [0, 0, 1500, 750]}]}'
    boxes, _ = b.parse_objects(text, ["can"], img_size=(3000, 1500))
    assert boxes == [box(0, 0, 0.5, 0.5)]
