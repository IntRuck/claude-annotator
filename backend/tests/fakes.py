"""In-memory repositories for service and router tests (no database).

Each fake follows the same contract as the real repository it replaces; the real ones are covered by the
`db` tests against Postgres.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

from annotator.activity.models import ActivityEntry
from annotator.classes.models import ProjectClass
from annotator.classes.repository import ClassNameTakenError
from annotator.image.models import Image
from annotator.job.models import OPEN, Job
from annotator.project.models import Project
from annotator.worker_status.models import EnginePause, WorkerStatus

NOW = datetime(2026, 11, 23, tzinfo=timezone.utc)


class FakeProjectRepository:
    def __init__(self):
        self.rows: dict[int, Project] = {}

    def list(self) -> list[Project]:
        return sorted(self.rows.values(), key=lambda p: p.id, reverse=True)

    def get(self, project_id: int) -> Project | None:
        return self.rows.get(project_id)

    def create(self, name: str, description: str = "") -> Project:
        project = Project(id=max(self.rows, default=0) + 1, name=name, description=description, created_at=NOW,
                          updated_at=NOW)
        self.rows[project.id] = project
        return project

    def save(self, project: Project) -> Project:
        self.rows[project.id] = project
        return project

    def delete(self, project_id: int) -> None:
        self.rows.pop(project_id, None)


class FakeClassRepository:
    def __init__(self):
        self.rows: dict[tuple[int, int], ProjectClass] = {}

    def list_for_project(self, project_id: int) -> list[ProjectClass]:
        return sorted((c for (p, _), c in self.rows.items() if p == project_id), key=lambda c: c.class_index)

    def get(self, project_id: int, class_index: int) -> ProjectClass | None:
        return self.rows.get((project_id, class_index))

    def count_by_project(self) -> dict[int, int]:
        counts: dict[int, int] = {}
        for project_id, _ in self.rows:
            counts[project_id] = counts.get(project_id, 0) + 1
        return counts

    def find_by_name(self, project_id: int, name: str) -> ProjectClass | None:
        return next((c for c in self.list_for_project(project_id) if c.name.lower() == name.lower()), None)

    def add(self, project_id: int, name: str, detector_prompt: str, description: str) -> ProjectClass:
        if self.find_by_name(project_id, name):
            raise ClassNameTakenError(name)
        index = len(self.list_for_project(project_id))
        row = ProjectClass(project_id=project_id, class_index=index, name=name,
                           detector_prompt=detector_prompt, description=description)
        self.rows[(project_id, index)] = row
        return row

    def save(self, row: ProjectClass) -> ProjectClass:
        clash = self.find_by_name(row.project_id, row.name)
        if clash is not None and clash.class_index != row.class_index:
            raise ClassNameTakenError(row.name)
        self.rows[(row.project_id, row.class_index)] = row
        return row


class FakeImageRepository:
    def __init__(self):
        self.rows: dict[int, Image] = {}

    def get(self, image_id: int) -> Image | None:
        return self.rows.get(image_id)

    def _of(self, project_id: int) -> list[Image]:
        return sorted((r for r in self.rows.values() if r.project_id == project_id), key=lambda r: r.file_name)

    def list_for_project(self, project_id: int, image_filter: str) -> list[Image]:
        rows = self._of(project_id)
        if image_filter == "flagged":
            return [r for r in rows if r.flagged]
        return rows if image_filter == "all" else [r for r in rows if r.status == image_filter]

    def counts(self, project_id: int) -> dict[str, int]:
        rows = self._of(project_id)
        counts = {"all": len(rows)}
        for key in ("unlabeled", "auto", "edited", "reviewed", "flagged", "error"):
            counts[key] = len(self.list_for_project(project_id, key))
        return counts

    def find_by_names(self, project_id: int, names: list[str]) -> list[Image]:
        return [r for r in self._of(project_id) if r.file_name in names]

    def summary_by_project(self) -> dict[int, dict]:
        summary = {}
        for project_id in sorted({r.project_id for r in self.rows.values()}):
            rows = self._of(project_id)
            summary[project_id] = {**self.counts(project_id), "last_changed_at": max(r.updated_at for r in rows),
                                   "cover_image_id": min(r.id for r in rows)}
        return summary

    def file_paths(self, project_id: int) -> list[str]:
        return [path for r in self._of(project_id) for path in (r.storage_path, r.thumb_path)]

    def ids_with_status(self, project_id: int, statuses: list[str] | None) -> list[int]:
        return [r.id for r in self._of(project_id) if statuses is None or r.status in statuses]

    def save(self, row: Image) -> Image:
        row.updated_at = NOW
        return row

    def add(self, project_id: int, *, file_name, stem, storage_path, thumb_path, width, height) -> Image:
        row = Image(id=len(self.rows) + 1, project_id=project_id, file_name=file_name, stem=stem,
                    storage_path=storage_path, thumb_path=thumb_path, width=width, height=height,
                    status="unlabeled", note="", flagged=False, flag_reason="", flag_note="", box_count=0,
                    created_at=NOW, updated_at=NOW)
        self.rows[row.id] = row
        return row


class FakeStorage:
    """Stores objects in a dict. Set `fail_with` to make every call raise that error."""

    def __init__(self):
        self.objects: dict[tuple[str, str], tuple[bytes, str]] = {}
        self.buckets: list[str] = []
        self.fail_with: Exception | None = None

    def _check(self):
        if self.fail_with:
            raise self.fail_with

    def ensure_bucket(self, bucket: str) -> None:
        self._check()
        if bucket not in self.buckets:
            self.buckets.append(bucket)

    def upload(self, bucket: str, path: str, data: bytes, content_type: str) -> None:
        self._check()
        self.objects[(bucket, path)] = (data, content_type)

    def download(self, bucket: str, path: str) -> bytes:
        self._check()
        return self.objects[(bucket, path)][0]

    def signed_url(self, bucket: str, path: str, expires_in: int) -> str:
        self._check()
        return f"http://storage.test/{bucket}/{path}?expires={expires_in}"

    def remove(self, bucket: str, paths: list[str]) -> None:
        self._check()
        for p in paths:
            self.objects.pop((bucket, p), None)


class FakeLabelRepository:
    """Boxes per image as plain dicts. Keeps the image's box_count in step, like the database trigger does."""

    def __init__(self, images: FakeImageRepository):
        self.images = images
        self.boxes: dict[int, list[dict]] = {}

    def list_for_image(self, image_id: int) -> list[dict]:
        return list(self.boxes.get(image_id, []))

    def list_for_project(self, project_id: int) -> list[SimpleNamespace]:
        """Rows shaped like Box (image_id, class_index, ...), by image and then in order."""
        return [SimpleNamespace(image_id=image_id, class_index=b["cls"], **{k: v for k, v in b.items() if k != "cls"})
                for image_id in sorted(self.boxes) if self.images.get(image_id).project_id == project_id
                for b in self.boxes[image_id]]

    def replace(self, project_id: int, image_id: int, boxes: list[dict], source: str):
        self.boxes[image_id] = [{**b, "source": b.get("source") or source} for b in boxes]
        self.images.get(image_id).box_count = len(boxes)
        return self.boxes[image_id]


class FakeJobRepository:
    """Jobs in a dict; same rules as the SQL (one open job per image, oldest queued claimed first, jobs of a paused
    engine wait). Pass the FakeWorkerStatusRepository that holds the pauses."""

    def __init__(self, pauses: "FakeWorkerStatusRepository | None" = None):
        self.rows: dict[int, Job] = {}
        self.pauses = pauses

    def get(self, job_id: int) -> Job | None:
        return self.rows.get(job_id)

    def enqueue(self, project_id, image_ids, *, kind, engine, options) -> list[int]:
        busy = {j.image_id for j in self.rows.values() if j.status in OPEN}
        ids = []
        for image_id in image_ids:
            if image_id in busy:
                continue
            job = Job(id=len(self.rows) + 1, project_id=project_id, image_id=image_id, kind=kind, engine=engine,
                      options=dict(options), status="queued", error="", created_at=NOW, started_at=None,
                      finished_at=None)
            self.rows[job.id] = job
            busy.add(image_id)
            ids.append(job.id)
        return ids

    def claim_next(self) -> Job | None:
        paused = set(self.pauses.paused) if self.pauses else set()
        queued = sorted((j for j in self.rows.values() if j.status == "queued" and j.engine not in paused),
                        key=lambda j: j.id)
        if not queued:
            return None
        queued[0].status, queued[0].started_at = "running", NOW
        return queued[0]

    def requeue(self, job_id):
        self.rows[job_id].status, self.rows[job_id].started_at = "queued", None

    def count_queued(self, project_id, engine=None) -> int:
        return sum(1 for j in self.rows.values() if j.project_id == project_id and j.status == "queued"
                   and (engine is None or j.engine == engine))

    def finish(self, job_id, status, error=""):
        job = self.rows.get(job_id)
        if job is not None:
            job.status, job.error, job.finished_at = status, error, NOW
        return job

    def cancel_queued(self, project_id, engine=None) -> int:
        hit = [j for j in self.rows.values() if j.project_id == project_id and j.status == "queued"
               and (engine is None or j.engine == engine)]
        for j in hit:
            j.status, j.finished_at = "cancelled", NOW
        return len(hit)

    def requeue_running(self) -> int:
        hit = [j for j in self.rows.values() if j.status == "running"]
        for j in hit:
            j.status, j.started_at = "queued", None
        return len(hit)

    def summary(self, project_id) -> dict:
        mine = sorted((j for j in self.rows.values() if j.project_id == project_id), key=lambda j: j.id)
        return {"queued": sum(j.status == "queued" for j in mine), "running": [j for j in mine if j.status == "running"]}


class FakeActivityRepository:
    def __init__(self):
        self.rows: list[ActivityEntry] = []

    def add(self, project_id, message, *, level="info", job_id=None, image_id=None) -> ActivityEntry:
        entry = ActivityEntry(id=len(self.rows) + 1, project_id=project_id, message=message, level=level,
                              job_id=job_id, image_id=image_id, created_at=NOW)
        self.rows.append(entry)
        return entry

    def get(self, entry_id):
        return next((e for e in self.rows if e.id == entry_id), None)

    def list_recent(self, project_id, limit):
        return [e for e in reversed(self.rows) if e.project_id == project_id][:limit]

    def messages(self, project_id=None) -> list[str]:
        return [e.message for e in self.rows if project_id is None or e.project_id == project_id]


class FakeWorkerStatusRepository:
    """Heartbeats and pauses in dicts. Move `clock` to make a heartbeat old."""

    def __init__(self):
        self.workers: dict[str, WorkerStatus] = {}
        self.paused: dict[str, EnginePause] = {}
        self.clock = NOW

    def heartbeat(self, worker_id, engines):
        row = self.workers.get(worker_id) or WorkerStatus(worker_id=worker_id, started_at=self.clock)
        row.engines, row.last_seen_at = engines, self.clock
        self.workers[worker_id] = row

    def remove(self, worker_id):
        self.workers.pop(worker_id, None)

    def latest(self):
        return max(self.workers.values(), key=lambda w: w.last_seen_at, default=None)

    def pauses(self):
        return sorted(self.paused.values(), key=lambda p: p.paused_at)

    def pause(self, engine, reason):
        row = self.paused.get(engine) or EnginePause(engine=engine, paused_at=self.clock)
        row.reason = reason
        self.paused[engine] = row

    def resume(self):
        engines = list(self.paused)
        self.paused.clear()
        return engines
