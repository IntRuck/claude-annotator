"""Labelling one image for a claimed job (today's Worker._run, one image at a time).

The worker calls it in three steps so no database transaction stays open while the engine works:
load (read) -> run_engine (no database) -> save (write), or fail / limit_reached.
"""
import time
from collections.abc import Callable
from dataclasses import dataclass

from annotator.activity.service import ActivityService
from annotator.classes.service import ClassService
from annotator.common.problem import ApiError
from annotator.image.service import ImageService
from annotator.job.schemas import JobOut
from annotator.job.service import JobService
from annotator.label.service import LabelService
from annotator.labeling.image_prep import prepare_for_vlm

EngineFactory = Callable[[str, dict], object]


@dataclass
class LabelTask:
    job: JobOut
    file_name: str
    image: bytes          # the original from Storage
    classes: list[str]    # names in index order, as the engine sees them
    prompts: list[str]    # what to look for: the detector prompt, else the name with _ as spaces
    descs: list[str]      # SKU descriptions
    indexes: list[int]    # class index of each position above


@dataclass
class LabelOutcome:
    boxes: list[dict]     # cls is the class index
    unknown: set[str]
    seconds: float
    engine: str


def run_engine(task: LabelTask, make_engine: EngineFactory) -> LabelOutcome:
    """Ask the engine for boxes. VLMs get a shrunk copy; detectors the original."""
    engine = make_engine(task.job.engine, task.job.options)
    image = prepare_for_vlm(task.image) if engine.resize_input else task.image
    started = time.monotonic()
    boxes, unknown = engine.annotate(image, task.classes, task.prompts, task.descs, task.job.options.get("extra", ""))
    mapped = [{**b, "cls": task.indexes[b["cls"]]} for b in boxes if 0 <= b["cls"] < len(task.indexes)]
    return LabelOutcome(mapped, set(unknown), time.monotonic() - started, engine.name)


def _reason(error: Exception | str) -> str:
    text = error.detail if isinstance(error, ApiError) else str(error)
    return (text or type(error).__name__)[:300]


class LabelingService:
    def __init__(self, jobs: JobService, images: ImageService, classes: ClassService, labels: LabelService,
                 activity: ActivityService):
        self.jobs = jobs
        self.images = images
        self.classes = classes
        self.labels = labels
        self.activity = activity

    def load(self, job: JobOut) -> LabelTask | None:
        """Everything the engine needs. None when the image was labelled by hand after a batch queued it."""
        image = self.images.get_image(job.image_id)
        only_if = job.options.get("onlyIfStatus")
        if only_if and image.status not in only_if:
            self.jobs.finish(job.id, "cancelled", f"skipped: the image is {image.status} now")
            self.activity.log(job.project_id, f"{image.file_name}: skipped, it was {image.status} by hand "
                                              "before its turn came", job_id=job.id, image_id=image.id)
            return None
        classes = self.classes.list_classes(job.project_id)
        return LabelTask(
            job=job, file_name=image.file_name, image=self.images.download_original(image.id),
            classes=[c.name for c in classes],
            prompts=[c.detector_prompt or c.name.replace("_", " ") for c in classes],
            descs=[c.description for c in classes],
            indexes=[c.index for c in classes],
        )

    def save(self, task: LabelTask, outcome: LabelOutcome) -> None:
        job = task.job
        kept = self.labels.replace_boxes(job.project_id, job.image_id, outcome.boxes, source="ai")
        note = f"via {outcome.engine}"
        if outcome.unknown:
            note += f"; unknown classes ignored: {', '.join(sorted(outcome.unknown))}"
        self.images.update_state(job.image_id, status="auto", note=note)
        self.jobs.finish(job.id, "done")
        self.activity.log(job.project_id, f"{task.file_name}: {kept} box(es) in {outcome.seconds:.1f}s ({note})",
                          job_id=job.id, image_id=job.image_id)

    def fail(self, job: JobOut, error: Exception | str) -> None:
        reason = _reason(error)
        self.jobs.finish(job.id, "failed", reason)
        try:
            image = self.images.update_state(job.image_id, status="error", note=f"{job.engine}: {reason}")
        except ApiError:
            return  # the image was deleted meanwhile
        self.activity.log(job.project_id, f"{image.file_name}: ERROR {reason}", level="error",
                          job_id=job.id, image_id=job.image_id)

    def limit_reached(self, job: JobOut, reason: str) -> None:
        self.jobs.stop_for_limit(job, reason)
