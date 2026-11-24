"""Which engines exist, the options each takes, and building one for a job.

More engines (Claude CLI, Ollama, Grounding DINO, YOLO-World) are added here in a later slice.
"""
from collections.abc import Callable
from dataclasses import dataclass

from annotator.common.text import one_line
from annotator.config.settings import Settings
from annotator.engine.gemini.client import DEFAULT_MODEL as GEMINI_DEFAULT_MODEL
from annotator.engine.gemini.client import GeminiEngine


class UnknownEngineError(ValueError):
    pass


@dataclass(frozen=True)
class EngineInfo:
    label: str
    defaults: dict
    build: Callable[[dict, Settings], object]


ENGINES: dict[str, EngineInfo] = {
    "gemini": EngineInfo(
        label="Gemini",
        defaults={"model": GEMINI_DEFAULT_MODEL, "extra": ""},
        build=lambda opts, s: GeminiEngine(opts["model"], api_key=s.gemini_api_key, base_url=s.gemini_base_url),
    ),
}


def _info(name: str) -> EngineInfo:
    if name not in ENGINES:
        raise UnknownEngineError(name)
    return ENGINES[name]


def clean_options(name: str, raw: dict) -> dict:
    """Only the options this engine takes, as one-line strings; blanks fall back to the defaults (extra may be blank)."""
    options = {}
    for key, default in _info(name).defaults.items():
        value = one_line(str(raw.get(key) or ""))
        options[key] = value or default
    return options


def make_engine(name: str, options: dict, settings: Settings):
    return _info(name).build(clean_options(name, options), settings)
