from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from annotator.engine.registry import ENGINES
from annotator.worker_status.repository import WorkerStatusRepository
from annotator.worker_status.schemas import EnginePauseOut, EngineState, EngineStatus, ResumeResult

# The worker beats every 15 s; three missed beats means it's gone.
OFFLINE_AFTER = timedelta(seconds=45)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WorkerStatusService:
    """Is the worker running, what can each engine do, and which engines are paused at a usage limit."""

    def __init__(self, repo: WorkerStatusRepository, now: Callable[[], datetime] = _utcnow):
        self.repo = repo
        self.now = now

    def status(self) -> EngineStatus:
        worker = self.repo.latest()
        reported = worker.engines if worker else {}
        engines = {}
        for name, info in ENGINES.items():
            seen = reported.get(name) or {}
            engines[name] = EngineState(label=info.label, ready=bool(seen.get("ready")), note=seen.get("note", ""),
                                        models=list(seen.get("models", [])), supports_refine=info.supports_refine)
        paused = [EnginePauseOut(engine=p.engine, label=ENGINES[p.engine].label if p.engine in ENGINES else p.engine,
                                 reason=p.reason, paused_at=p.paused_at) for p in self.repo.pauses()]
        online = worker is not None and self.now() - worker.last_seen_at <= OFFLINE_AFTER
        return EngineStatus(worker_online=online, last_seen_at=worker.last_seen_at if worker else None,
                            engines=engines, paused=paused)

    def pause(self, engine: str, reason: str) -> None:
        self.repo.pause(engine, reason[:500])

    def resume(self) -> ResumeResult:
        return ResumeResult(resumed=sorted(self.repo.resume()))

    # ---------- worker side ----------
    def heartbeat(self, worker_id: str, engines: dict) -> None:
        self.repo.heartbeat(worker_id, engines)

    def stopped(self, worker_id: str) -> None:
        self.repo.remove(worker_id)
