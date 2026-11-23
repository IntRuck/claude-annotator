"""Characterisation tests for today's app (app.py + backends.py at the repo root).

They pin down current behaviour so the code can move into annotator/ without changing it.
Removed together with the old files at the end of the v2 switch-over.
"""
import os
import sys
from pathlib import Path

import pytest
from PIL import Image

# LEGACY_ROOT lets a mutation check point these tests at a modified copy of app.py/backends.py.
REPO_ROOT = Path(os.environ.get("LEGACY_ROOT") or Path(__file__).resolve().parents[3])
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def make_image():
    def _make(path: Path, size=(100, 50), color=(120, 120, 120)):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, color).save(path)
        return path

    return _make


@pytest.fixture
def project(tmp_path, make_image):
    """A dataset with classes can/bottle and four 100x50 images a-d, no labels yet."""
    import app

    images = tmp_path / "images"
    for name in ("a.jpg", "b.jpg", "c.jpg", "d.jpg"):
        make_image(images / name)
    classes = tmp_path / "classes.txt"
    classes.write_text("can\nbottle\n", encoding="utf-8")
    return app.Project(images, tmp_path / "labels", classes)
