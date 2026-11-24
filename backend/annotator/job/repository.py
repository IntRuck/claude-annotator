from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from annotator.job.models import OPEN, Job
from annotator.worker_status.models import EnginePause


class JobRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, job_id: int) -> Job | None:
        return self.session.get(Job, job_id)

    def enqueue(self, project_id: int, image_ids: list[int], *, kind: str, engine: str, options: dict) -> list[int]:
        """One job per image, in the order given, in a single statement (one live-update message).
        Images that already have a queued or running job are skipped. Returns the new job ids."""
        if not image_ids:
            return []
        rows = [{"project_id": project_id, "image_id": i, "kind": kind, "engine": engine, "options": options}
                for i in image_ids]
        stmt = (insert(Job).values(rows)
                .on_conflict_do_nothing(index_elements=[Job.image_id], index_where=Job.status.in_(OPEN))
                .returning(Job.id))
        return sorted(self.session.scalars(stmt))

    def claim_next(self) -> Job | None:
        """The oldest queued job of an engine that isn't paused, now running.
        SKIP LOCKED: a job another worker holds is passed over."""
        paused = select(EnginePause.engine)
        oldest = (select(Job.id).where(Job.status == "queued", Job.engine.not_in(paused)).order_by(Job.id)
                  .limit(1).with_for_update(skip_locked=True).scalar_subquery())
        stmt = (update(Job).where(Job.id == oldest)
                .values(status="running", started_at=func.clock_timestamp())
                .returning(Job))
        return self.session.scalars(stmt).one_or_none()

    def finish(self, job_id: int, status: str, error: str = "") -> Job | None:
        stmt = (update(Job).where(Job.id == job_id)
                .values(status=status, error=error, finished_at=func.clock_timestamp())
                .returning(Job))
        return self.session.scalars(stmt).one_or_none()

    def cancel_queued(self, project_id: int, engine: str | None = None) -> int:
        stmt = update(Job).where(Job.project_id == project_id, Job.status == "queued")
        if engine is not None:
            stmt = stmt.where(Job.engine == engine)
        stmt = stmt.values(status="cancelled", finished_at=func.clock_timestamp())
        return self.session.execute(stmt).rowcount

    def requeue(self, job_id: int) -> None:
        """One job back to the queue (its engine hit a usage limit)."""
        self.session.execute(update(Job).where(Job.id == job_id).values(status="queued", started_at=None))

    def count_queued(self, project_id: int, engine: str | None = None) -> int:
        stmt = select(func.count()).where(Job.project_id == project_id, Job.status == "queued")
        if engine is not None:
            stmt = stmt.where(Job.engine == engine)
        return self.session.scalar(stmt)

    def requeue_running(self) -> int:
        """After a worker crash or restart: jobs it was running go back to the queue."""
        stmt = update(Job).where(Job.status == "running").values(status="queued", started_at=None)
        return self.session.execute(stmt).rowcount

    def summary(self, project_id: int) -> dict:
        queued = self.session.scalar(
            select(func.count()).where(Job.project_id == project_id, Job.status == "queued"))
        running = list(self.session.scalars(
            select(Job).where(Job.project_id == project_id, Job.status == "running").order_by(Job.id)))
        return {"queued": queued, "running": running}
