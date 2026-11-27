"""Which images go into an export (today's rules): labelled ones, optionally approved only and without flagged ones."""
from dataclasses import dataclass
from typing import Any

from annotator.label.rules import is_labelled


@dataclass(frozen=True)
class Picked:
    number: int        # position in the project's whole image list, from 1 (today's COCO image id)
    image: Any         # has id, file_name, width, height, status, flagged
    boxes: list[dict]  # {cls, x1, y1, x2, y2}, 0-1


def pick(images: list, boxes_by_image: dict[int, list[dict]], *, only_reviewed: bool = False,
         skip_flagged: bool = False) -> list[Picked]:
    """`images` in display order (by file name). Unlabelled images are always left out."""
    picked = []
    for number, img in enumerate(images, start=1):
        boxes = boxes_by_image.get(img.id, [])
        if not is_labelled(img.status, len(boxes)):
            continue
        if only_reviewed and img.status != "reviewed":
            continue
        if skip_flagged and img.flagged:
            continue
        picked.append(Picked(number, img, boxes))
    return picked


def fully_outlined(picked: list[Picked]) -> tuple[list[Picked], int]:
    """For an outline export: keep images whose every object has an outline (images without objects stay, as
    background). A half-outlined image would teach the model that the other products are background.
    Returns (kept, how many were left out)."""
    kept = [p for p in picked if all(b.get("points") for b in p.boxes)]
    return kept, len(picked) - len(kept)
