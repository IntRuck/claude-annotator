from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from annotator.worker_status.models import EnginePause, WorkerStatus


class WorkerStatusRepository:
    def __init__(self, session: Session):
        self.session = session

    def heartbeat(self, worker_id: str, engines: dict) -> None:
        stmt = insert(WorkerStatus).values(worker_id=worker_id, engines=engines, last_seen_at=func.clock_timestamp())
        stmt = stmt.on_conflict_do_update(index_elements=[WorkerStatus.worker_id],
                                          set_={"engines": stmt.excluded.engines,
                                                "last_seen_at": func.clock_timestamp()})
        self.session.execute(stmt)

    def remove(self, worker_id: str) -> None:
        self.session.execute(delete(WorkerStatus).where(WorkerStatus.worker_id == worker_id))

    def latest(self) -> WorkerStatus | None:
        stmt = select(WorkerStatus).order_by(WorkerStatus.last_seen_at.desc()).limit(1)
        return self.session.scalars(stmt, execution_options={"populate_existing": True}).first()

    def pauses(self) -> list[EnginePause]:
        stmt = select(EnginePause).order_by(EnginePause.paused_at)
        return list(self.session.scalars(stmt, execution_options={"populate_existing": True}))

    def pause(self, engine: str, reason: str) -> None:
        stmt = insert(EnginePause).values(engine=engine, reason=reason)
        stmt = stmt.on_conflict_do_update(index_elements=[EnginePause.engine], set_={"reason": stmt.excluded.reason})
        self.session.execute(stmt)

    def resume(self) -> list[str]:
        return list(self.session.scalars(delete(EnginePause).returning(EnginePause.engine)))
