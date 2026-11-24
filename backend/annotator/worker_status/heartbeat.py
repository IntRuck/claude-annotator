"""The worker's heartbeat (like today's availability() check, sent every few seconds instead of asked for).

Each beat stores what every engine can do right now; the engine check itself (which may call Google for the
model list) runs much less often.
"""
import logging
import threading
import time
from collections.abc import Callable

from annotator.config.settings import Settings

log = logging.getLogger(__name__)

NO_GEMINI_KEY = ("No Gemini API key. Put GEMINI_API_KEY=... in the backend's env file (see .env.example), "
                 "then restart the worker.")


def engine_availability(settings: Settings, list_gemini_models: Callable[[], list[str]]) -> dict[str, dict]:
    """{engine: {"ready", "note", "models"}} for the engines the worker can run."""
    if not settings.gemini_api_key.strip():
        gemini = {"ready": False, "note": NO_GEMINI_KEY, "models": []}
    else:
        try:
            gemini = {"ready": True, "note": "", "models": list_gemini_models()}
        except Exception as e:
            gemini = {"ready": True, "note": f"Couldn't list Gemini models: {e}"[:300], "models": []}
    return {"gemini": gemini}


class Heartbeat:
    def __init__(self, beat: Callable[[dict], None], gone: Callable[[], None], availability: Callable[[], dict], *,
                 every: float = 15.0, refresh_every: float = 600.0):
        self.beat = beat
        self.gone = gone
        self.availability = availability
        self.every = every
        self.refresh_every = refresh_every
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="heartbeat", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout)

    def _run(self) -> None:
        engines, checked_at = None, 0.0
        while not self._stop.is_set():
            if engines is None or time.monotonic() - checked_at >= self.refresh_every:
                engines, checked_at = self._check(), time.monotonic()
            try:
                self.beat(engines)
            except Exception:
                log.exception("Heartbeat failed (database down?); trying again")
            self._stop.wait(self.every)
        try:
            self.gone()
        except Exception:
            log.exception("Couldn't remove the worker's heartbeat row")

    def _check(self) -> dict:
        try:
            return self.availability()
        except Exception:
            log.exception("Engine check failed")
            return {}
