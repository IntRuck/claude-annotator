import pytest

from annotator.label.service import LabelService
from tests.fakes import FakeImageRepository, FakeLabelRepository


@pytest.fixture
def images():
    repo = FakeImageRepository()
    repo.add(1, file_name="a.jpg", stem="a", storage_path="p", thumb_path="t", width=100, height=50)
    return repo


def test_replace_boxes_applies_the_save_rules_and_returns_how_many_were_kept(images):
    labels = FakeLabelRepository(images)
    kept = LabelService(labels).replace_boxes(1, 1, [
        {"cls": 0, "x1": 0.5, "y1": 0.5, "x2": 0.1, "y2": 0.1},
        {"cls": 1, "x1": 0.2, "y1": 0.2, "x2": 0.2005, "y2": 0.9},
    ], source="import")
    assert kept == 1
    assert labels.boxes[1] == [pytest.approx({"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5, "source": "import"})]
    assert images.get(1).box_count == 1
