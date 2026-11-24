"""The worker's loop: claim the oldest job, label its image, repeat; sleep until woken when the queue is empty.

Each step runs in its own short unit of work (session + commit), so nothing holds a transaction while an
engine thinks for seconds or minutes. A NOTIFY on the jobs table sets `wake`; `idle_seconds` is the fallback.
"""
import logging
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager

from annotator.engine.base import LimitReached
from annotator.labeling.service import EngineFactory, run_engine

log = logging.getLogger(__name__)


class JobLoop:
    def __init__(self, unit: Callable[[], AbstractContextManager], make_engine: EngineFactory, *,
                 wake: threading.Event, stop: threading.Event, idle_seconds: float = 5.0):
        """`unit()` yields an object with `.jobs` (JobService) and `.labeling` (LabelingService) and commits on exit."""
        self.unit = unit
        self.make_engine = make_engine
        self.wake = wake
        self.stop = stop
        self.idle_seconds = idle_seconds

    def run_forever(self) -> None:
        with self.unit() as s:
            recovered = s.jobs.recover()
        if recovered:
            log.info("Put %d interrupted job(s) back in the queue", recovered)
        while not self.stop.is_set():
            try:
                worked = self.run_once()
            except Exception:
                log.exception("Worker step failed (database down?); trying again shortly")
                worked = False
            if not worked and not self.stop.is_set():
                self.wake.wait(self.idle_seconds)
                self.wake.clear()

    def run_once(self) -> bool:
        """Label one queued image. False when the queue is empty."""
        with self.unit() as s:
            job = s.jobs.claim_next()
        if job is None:
            return False
        try:
            with self.unit() as s:
                task = s.labeling.load(job)
            if task is None:
                return True
            outcome = run_engine(task, self.make_engine)      # no database while the engine works
            with self.unit() as s:
                s.labeling.save(task, outcome)
        except LimitReached as e:
            log.warning("Job %s: usage limit: %s", job.id, e)
            self._safely(lambda s: s.labeling.limit_reached(job, str(e)))
        except Exception as e:
            log.warning("Job %s failed: %s", job.id, e)
            self._safely(lambda s: s.labeling.fail(job, e))
        return True

    def _safely(self, step) -> None:
        try:
            with self.unit() as s:
                step(s)
        except Exception:
            # The job stays "running"; the next worker start puts it back in the queue.
            log.exception("Couldn't record the outcome of a failed job")
