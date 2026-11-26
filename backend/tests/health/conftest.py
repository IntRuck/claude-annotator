"""A project with classes can + bottle and two images: b.jpg (id 1, unlabeled) and a.jpg (id 2, auto, 2 cans)."""
import pytest

from annotator.classes.schemas import ClassCreate
from annotator.classes.service import ClassService
from annotator.health.service import HealthService
from annotator.image.service import ImageService
from annotator.label.service import LabelService
from annotator.project.service import ProjectService
from tests.fakes import (
    FakeClassRepository,
    FakeImageRepository,
    FakeLabelRepository,
    FakeProjectRepository,
    FakeStorage,
)

CAN = {"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.3, "y2": 0.3}


@pytest.fixture
def service():
    projects = ProjectService(FakeProjectRepository())
    projects.create_project("Shelf")
    classes = ClassService(FakeClassRepository(), projects)
    for name in ("can", "bottle"):
        classes.add_class(1, ClassCreate(name=name))
    images_repo = FakeImageRepository()
    images = ImageService(images_repo, FakeStorage(), projects)
    labels = LabelService(FakeLabelRepository(images_repo), images, classes)
    for name in ("b.jpg", "a.jpg"):
        images_repo.add(1, file_name=name, stem=name[0], storage_path="p", thumb_path="t", width=100, height=50)
    labels.replace_boxes(1, 2, [CAN, dict(CAN, x1=0.5, x2=0.7)], source="ai")  # a.jpg
    images.update_state(2, status="auto")
    return HealthService(images, classes, labels)
