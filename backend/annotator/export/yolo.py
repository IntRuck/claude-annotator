"""YOLO dataset zip, moved from today's app.export_yolo_zip:
dataset/images/{train,val}/<file>, dataset/labels/{train,val}/<stem>.txt and dataset/data.yaml."""
import json
import random
import re
import zipfile
from collections.abc import Callable
from pathlib import PurePosixPath
from typing import BinaryIO

from annotator.export.pick import Picked

VAL_RATIO = 0.1
SEED = 0
_PLAIN_YAML = re.compile(r"^[^\s:#'\"{}\[\],&*!|>%@`?-][^:#'\"{}\[\],&*!|>%@`]*$")


def split(picked: list[Picked], val_ratio: float = VAL_RATIO, seed: int = SEED) -> dict[int, str]:
    """Image id -> "train" or "val". Today's split: shuffle with a fixed seed, the first int(n * ratio) are val."""
    order = list(picked)
    random.Random(seed).shuffle(order)
    n_val = int(len(order) * val_ratio)
    return {p.image.id: ("val" if i < n_val else "train") for i, p in enumerate(order)}


def label_text(boxes: list[dict]) -> str:
    """One `class cx cy w h` line per box (0-1, 6 decimals), like today's label files; empty for no boxes."""
    lines = [f"{int(b['cls'])} {(b['x1'] + b['x2']) / 2:.6f} {(b['y1'] + b['y2']) / 2:.6f} "
             f"{b['x2'] - b['x1']:.6f} {b['y2'] - b['y1']:.6f}" for b in boxes]
    return "\n".join(lines) + ("\n" if lines else "")


def _yaml_name(name: str) -> str:
    # Plain names stay as today; a name YAML would misread (e.g. "Coke: 330ml") is double-quoted.
    return name if _PLAIN_YAML.match(name) and name == name.strip() else json.dumps(name, ensure_ascii=False)


def data_yaml(classes: list[tuple[int, str]]) -> str:
    return ("path: .\ntrain: images/train\nval: images/val\n\nnames:\n"
            + "".join(f"  {index}: {_yaml_name(name)}\n" for index, name in classes))


def write_zip(out: BinaryIO, classes: list[tuple[int, str]], picked: list[Picked],
              read_image: Callable[[object], bytes], *, val_ratio: float = VAL_RATIO, seed: int = SEED) -> None:
    """Write the zip to `out`. `read_image(image)` returns the original photo's bytes."""
    where = split(picked, val_ratio, seed)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in picked:
            part = where[p.image.id]
            z.writestr(f"dataset/images/{part}/{p.image.file_name}", read_image(p.image))
            z.writestr(f"dataset/labels/{part}/{PurePosixPath(p.image.file_name).stem}.txt", label_text(p.boxes))
        z.writestr("dataset/data.yaml", data_yaml(classes))
