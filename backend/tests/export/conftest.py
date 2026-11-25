"""A project with classes can + bottle and three images, originals in (fake) storage:
  1 a.jpg  auto, two can boxes
  2 b.jpg  reviewed, one bottle box
  3 c.jpg  auto, flagged, one can box
  4 d.jpg  unlabeled
"""
import pytest

from annotator.classes.schemas import ClassCreate
from annotator.classes.service import ClassService
from annotator.export.service import ExportService
from annotator.image.service import ImageService
from annotator.label.service import LabelService
from annotator.project.service import ProjectService
from annotator.storage.storage_service import IMAGES_BUCKET
from tests.fakes import FakeClassRepository, FakeImageRepository, FakeLabelRepository, FakeProjectRepository, FakeStorage

CAN = {"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.3, "y2": 0.3}
BOTTLE = {"cls": 1, "x1": 0.5, "y1": 0.5, "x2": 0.9, "y2": 0.9}


@pytest.fixture
def world():
    projects = ProjectService(FakeProjectRepository())
    projects.create_project("Shelf")
    classes = ClassService(FakeClassRepository(), projects)
    for name in ("can", "bottle"):
        classes.add_class(1, ClassCreate(name=name))
    storage = FakeStorage()
    images_repo = FakeImageRepository()
    images = ImageService(images_repo, storage, projects)
    labels = LabelService(FakeLabelRepository(images_repo), images, classes)
    for name in ("a.jpg", "b.jpg", "c.jpg", "d.jpg"):
        images_repo.add(1, file_name=name, stem=name[0], storage_path=f"1/{name}", thumb_path="t", width=100, height=50)
        storage.upload(IMAGES_BUCKET, f"1/{name}", f"pixels of {name}".encode(), "image/jpeg")
    labels.replace_boxes(1, 1, [CAN, CAN], source="ai")
    labels.replace_boxes(1, 2, [BOTTLE], source="human")
    labels.replace_boxes(1, 3, [CAN], source="ai")
    images.update_state(1, status="auto")
    images.update_state(2, status="reviewed")
    images.update_state(3, status="auto", flagged=True)
    return ExportService(images, classes, labels), storage


@pytest.fixture
def service(world):
    return world[0]
