"""The worker's heartbeat (like today's availability() check, sent every few seconds instead of asked for).

Each beat stores what every engine can do right now. The engine check runs about once a minute, so starting Ollama
shows up quickly; the Gemini model list (a call to Google) is asked for less often (`cached_for`).
"""
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from annotator.config.settings import Settings
from annotator.engine.claude_cli.client import NOT_FOUND as NO_CLAUDE_CLI
from annotator.engine.ollama.client import DEFAULT_MODEL as OLLAMA_DEFAULT_MODEL

log = logging.getLogger(__name__)

NO_GEMINI_KEY = ("No Gemini API key. Put GEMINI_API_KEY=... in the backend's env file (see .env.example), "
                 "then restart the worker.")
NO_DETECTORS = ('Not installed. Install PyTorch (with CUDA, see pytorch.org), then in backend: '
                '.venv/Scripts/python -m pip install -e ".[detectors]", and restart the worker.')
CPU_ONLY = "No CUDA GPU found: it runs on the CPU (slow)."


@dataclass
class Probes:
    """How the worker looks at each engine (the real checks are wired in worker.py)."""
    gemini_models: Callable[[], list[str]]      # what the key can use; raises with the reason
    ollama_models: Callable[[], list[str]]      # what's pulled; raises when Ollama isn't running
    claude_path: Callable[[], str | None]       # where the claude CLI is, None when not found
    installed: Callable[..., bool]              # are these packages installed?
    cuda: Callable[[], bool]                    # is there a CUDA GPU? (imports torch)


def _state(ready: bool, note: str = "", models: list[str] | None = None) -> dict:
    return {"ready": ready, "note": note[:300], "models": models or []}


def _gemini(settings: Settings, models: Callable[[], list[str]]) -> dict:
    if not settings.gemini_api_key.strip():
        return _state(False, NO_GEMINI_KEY)
    try:
        return _state(True, models=models())
    except Exception as e:
        return _state(True, f"Couldn't list Gemini models: {e}")


def _ollama(settings: Settings, models: Callable[[], list[str]]) -> dict:
    try:
        pulled = models()
    except Exception:
        return _state(False, f"Ollama isn't running at {settings.ollama_url.rstrip('/')}. Start it (ollama serve) "
                             f"and pull a model (ollama pull {OLLAMA_DEFAULT_MODEL}).")
    if not pulled:
        return _state(False, f"Ollama has no models yet. Pull one: ollama pull {OLLAMA_DEFAULT_MODEL}")
    return _state(True, models=pulled)


def _detector(installed: bool, cuda: Callable[[], bool]) -> dict:
    if not installed:
        return _state(False, NO_DETECTORS)
    return _state(True, "" if cuda() else CPU_ONLY)


def engine_availability(settings: Settings, probes: Probes) -> dict[str, dict]:
    """{engine: {"ready", "note", "models"}} for every engine the worker can run."""
    return {
        "gemini": _gemini(settings, probes.gemini_models),
        "claude": _state(True) if probes.claude_path() else _state(False, NO_CLAUDE_CLI),
        "ollama": _ollama(settings, probes.ollama_models),
        "grounding_dino": _detector(probes.installed("torch", "transformers"), probes.cuda),
        "yolo_world": _detector(probes.installed("ultralytics"), probes.cuda),
    }


def cached_for(seconds: float, ask: Callable[[], list[str]],
               clock: Callable[[], float] = time.monotonic) -> Callable[[], list[str]]:
    """`ask`'s last answer, asked again once it is `seconds` old. A failure isn't kept, so the next check retries."""
    kept: dict = {}

    def answer():
        if "value" not in kept or clock() - kept["at"] >= seconds:
            kept["value"], kept["at"] = ask(), clock()
        return kept["value"]

    return answer


class Heartbeat:
    def __init__(self, beat: Callable[[dict], None], gone: Callable[[], None], availability: Callable[[], dict], *,
                 every: float = 15.0, refresh_every: float = 60.0):
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
