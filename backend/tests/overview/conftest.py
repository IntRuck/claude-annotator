"""Projects "Shelf" (id 1: SKUs can + bottle, images a.jpg reviewed, b.jpg auto + flagged, c.jpg unlabeled,
d.jpg error) and "Empty" (id 2: nothing yet). Photos are uploaded to a FakeStorage so delete can be checked."""
from datetime import timedelta
from types import SimpleNamespace

import pytest

from annotator.classes.schemas import ClassCreate
from annotator.classes.service import ClassService
from annotator.image.service import ImageService
from annotator.overview.service import OverviewService
from annotator.project.service import ProjectService
from tests.fakes import NOW, FakeClassRepository, FakeImageRepository, FakeProjectRepository, FakeStorage


@pytest.fixture
def world():
    project_repo, image_repo, storage = FakeProjectRepository(), FakeImageRepository(), FakeStorage()
    projects = ProjectService(project_repo)
    projects.create_project("Shelf", "Store 3")
    projects.create_project("Empty")
    classes = ClassService(FakeClassRepository(), projects)
    for name in ("can", "bottle"):
        classes.add_class(1, ClassCreate(name=name))
    images = ImageService(image_repo, storage, projects)
    for name in ("a.jpg", "b.jpg", "c.jpg", "d.jpg"):
        path = f"1/{name}"
        image_repo.add(1, file_name=name, stem=name[0], storage_path=path, thumb_path=f"1/thumbs/{name}",
                       width=10, height=10)
        storage.upload("images", path, b"x", "image/jpeg")
        storage.upload("images", f"1/thumbs/{name}", b"x", "image/jpeg")
    images.update_state(1, status="reviewed")
    images.update_state(2, status="auto", flagged=True)
    images.update_state(4, status="error")
    image_repo.get(2).updated_at = NOW + timedelta(hours=2)
    return SimpleNamespace(service=OverviewService(projects, images, classes), projects=project_repo,
                           images=image_repo, storage=storage)
