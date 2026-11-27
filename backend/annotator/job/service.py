from annotator.activity.service import ActivityService
from annotator.classes.service import ClassService
from annotator.common.problem import ApiError
from annotator.engine.registry import ENGINES, UnknownEngineError, clean_options
from annotator.image.service import ImageService
from annotator.job.repository import JobRepository
from annotator.job.schemas import JobCreate, JobOut, JobSummary, QueueResult, RunningJob, StopResult
from annotator.label.service import LabelService
from annotator.project.service import ProjectService

# Statuses each target picks, per kind (today's buttons: Label all unlabeled, Find objects / Refine boxes with AI,
# Refine all). Batch targets also re-check the status when the image's turn comes, so an image labelled by hand
# in the meantime isn't overwritten. "image" and "all" overwrite on purpose.
TARGETS: dict[str, dict[str, list[str] | None]] = {
    "annotate": {"image": None, "unlabeled": ["unlabeled", "error"], "errors": ["error"], "all": None},
    "refine": {"image": None, "auto": ["auto"]},
}
PROTECTED_TARGETS = ("unlabeled", "errors", "auto")


def engine_label(engine: str) -> str:
    return ENGINES[engine].label if engine in ENGINES else engine


class JobService:
    """The AI work queue: one job per image. The API queues and stops; the worker claims and finishes."""

    def __init__(self, repo: JobRepository, projects: ProjectService, images: ImageService, classes: ClassService,
                 activity: ActivityService, labels: LabelService):
        self.repo = repo
        self.projects = projects
        self.images = images
        self.classes = classes
        self.activity = activity
        self.labels = labels

    # ---------- API side ----------
    def queue(self, project_id: int, body: JobCreate) -> QueueResult:
        self.projects.get_project(project_id)
        targets = TARGETS[body.kind]          # JobCreate only lets known kinds and targets through
        if body.target not in targets:
            raise ApiError(400, "UNKNOWN_TARGET",
                           f"Unknown target '{body.target}' for {body.kind}. Use one of: {', '.join(targets)}.")
        try:
            options = clean_options(body.engine, body.options)
        except UnknownEngineError:
            raise ApiError(400, "UNKNOWN_ENGINE",
                           f"Unknown engine '{body.engine}'. Use one of: {', '.join(ENGINES)}.") from None
        if body.kind == "refine" and not ENGINES[body.engine].supports_refine:
            raise ApiError(400, "CANT_REFINE", f"{engine_label(body.engine)} can't refine boxes; use a VLM "
                                               "such as Gemini, Claude or a local Ollama model.")
        if not self.classes.list_classes(project_id):
            raise ApiError(400, "NO_CLASSES", "Add at least one class (SKU) first, so the AI knows what to look for.")

        image_ids = self._target_ids(project_id, body)
        if body.target in PROTECTED_TARGETS:
            options["onlyIfStatus"] = targets[body.target]
        queued = self.repo.enqueue(project_id, image_ids, kind=body.kind, engine=body.engine, options=options)

        waiting = len(image_ids) - len(queued)
        if queued:
            how = "to refine with" if body.kind == "refine" else "for"
            line = f"Queued {len(queued)} image(s) {how} {engine_label(body.engine)} ({options['model']})"
            self.activity.log(project_id, line + (f"; {waiting} already waiting" if waiting else ""))
        return QueueResult(matched=len(image_ids), queued=len(queued), already_queued=waiting)

    def _target_ids(self, project_id: int, body: JobCreate) -> list[int]:
        if body.target != "image":
            ids = self.images.ids_with_status(project_id, TARGETS[body.kind][body.target])
            if body.target in PROTECTED_TARGETS:
                # The AI replaces every object, outlines too: batches never touch an outlined image.
                outlined = self.labels.image_ids_with_outlines(project_id)
                ids = [i for i in ids if i not in outlined]
            return ids
        if body.image_id is None:
            raise ApiError(400, "IMAGE_REQUIRED", "Say which image to label (imageId).")
        image = self.images.get_image(body.image_id)
        if image.project_id != project_id:
            raise ApiError(404, "IMAGE_NOT_FOUND", f"Image {body.image_id} doesn't exist in this project.")
        return [image.id]

    def stop(self, project_id: int) -> StopResult:
        self.projects.get_project(project_id)
        cancelled = self.repo.cancel_queued(project_id)
        if cancelled:
            self.activity.log(project_id, f"Stopped: {cancelled} waiting image(s) cancelled. "
                                          "The image being labelled now finishes first.")
        return StopResult(cancelled=cancelled)

    def summary(self, project_id: int) -> JobSummary:
        raw = self.repo.summary(project_id)
        running = []
        for job in raw["running"]:
            file_name = self.images.get_image(job.image_id).file_name if job.image_id else ""
            running.append(RunningJob(id=job.id, image_id=job.image_id, file_name=file_name, engine=job.engine,
                                      kind=job.kind, started_at=job.started_at))
        return JobSummary(queued=raw["queued"], running=running)

    # ---------- worker side ----------
    def claim_next(self) -> JobOut | None:
        job = self.repo.claim_next()
        return JobOut.model_validate(job) if job else None

    def finish(self, job_id: int, status: str, error: str = "") -> None:
        self.repo.finish(job_id, status, error[:1000])

    def recover(self) -> int:
        """Jobs a stopped or crashed worker was running go back to the queue."""
        return self.repo.requeue_running()

    def requeue(self, job_id: int) -> None:
        """Back to the queue untouched (its engine hit a usage limit)."""
        self.repo.requeue(job_id)

    def count_queued(self, project_id: int, engine: str | None = None) -> int:
        return self.repo.count_queued(project_id, engine)
