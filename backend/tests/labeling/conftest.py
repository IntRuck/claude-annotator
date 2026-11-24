"""A small world of fakes for labelling and the job loop: project 1 with classes, images, jobs and a fake engine."""
import io

import pytest
from PIL import Image

from annotator.activity.service import ActivityService
from annotator.classes.schemas import ClassCreate
from annotator.classes.service import ClassService
from annotator.image.service import ImageService, UploadedFile
from annotator.job.schemas import JobCreate
from annotator.job.service import JobService
from annotator.label.service import LabelService
from annotator.labeling.service import LabelingService
from annotator.project.service import ProjectService
from tests.fakes import (FakeActivityRepository, FakeClassRepository, FakeImageRepository, FakeJobRepository,
                         FakeLabelRepository, FakeProjectRepository, FakeStorage)


def jpeg(size=(100, 50)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size).save(buf, format="JPEG")
    return buf.getvalue()


class FakeEngine:
    """Answers each annotate call from a script: (boxes, unknown) tuples or exceptions. Records what it saw."""

    name = "gemini"
    supports_refine = True

    def __init__(self, script, resize_input=True):
        self.script = list(script)
        self.resize_input = resize_input
        self.calls = []

    def annotate(self, image, classes, prompts, descs, extra):
        self.calls.append({"image": image, "classes": classes, "prompts": prompts, "descs": descs, "extra": extra})
        out = self.script.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


class World:
    def __init__(self):
        self.projects = ProjectService(FakeProjectRepository())
        self.projects.create_project("Shelf")
        self.class_repo = FakeClassRepository()
        self.classes = ClassService(self.class_repo, self.projects)
        self.classes.add_class(1, ClassCreate(name="tuna_can", description="red tin"))
        self.classes.add_class(1, ClassCreate(name="jar", detector_prompt="glass jar"))
        self.storage = FakeStorage()
        self.image_repo = FakeImageRepository()
        self.images = ImageService(self.image_repo, self.storage, self.projects)
        self.label_repo = FakeLabelRepository(self.image_repo)
        self.labels = LabelService(self.label_repo, self.images, self.classes)
        self.activity_repo = FakeActivityRepository()
        self.activity = ActivityService(self.activity_repo, self.projects)
        self.job_repo = FakeJobRepository()
        self.jobs = JobService(self.job_repo, self.projects, self.images, self.classes, self.activity)
        self.labeling = LabelingService(self.jobs, self.images, self.classes, self.labels, self.activity)
        self.engine = FakeEngine([])

    def make_engine(self, name, options):
        return self.engine

    def upload(self, name, size=(100, 50)):
        return self.images.upload(1, [UploadedFile(name, jpeg(size), "image/jpeg")]).added[0].id

    def queue(self, target="unlabeled", **kw):
        return self.jobs.queue(1, JobCreate(target=target, options={"model": "gemini-x", "extra": "top shelf"}, **kw))

    def status(self, image_id):
        return self.image_repo.get(image_id).status


@pytest.fixture
def w():
    return World()
