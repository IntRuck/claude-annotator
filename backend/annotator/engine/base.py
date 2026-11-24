"""What every engine shares.

An engine has `name`, `label`, `supports_refine`, `resize_input` and
    annotate(image, classes, prompts, descs, extra) -> (boxes, unknown_names)
`image` is JPEG/PNG bytes, `classes` the class names in index order, `prompts` what to look for (the detector
prompt, else the name with _ as spaces) and `descs` the SKU descriptions. `boxes` are dicts
{"cls": position in `classes`, "x1", "y1", "x2", "y2": 0-1, "conf": optional}; `unknown_names` are labels
the model used that aren't classes.
"""


class LimitReached(Exception):
    """A usage limit or quota was hit: stop sending work to this engine until it resets."""
