"""Which engines exist, the options each takes, and building one for a job.

An engine's `defaults` say which options it takes and their type: text (one line), a switch (True/False) or a
confidence (a float). Detectors import torch only when they run, so this module loads without it.
"""
import math
from collections.abc import Callable
from dataclasses import dataclass

from annotator.common.text import one_line
from annotator.config.settings import Settings
from annotator.engine.claude_cli.client import DEFAULT_MODEL as CLAUDE_DEFAULT_MODEL
from annotator.engine.claude_cli.client import ClaudeCliEngine
from annotator.engine.detectors.grounding_dino import DEFAULT_MODEL as DINO_DEFAULT_MODEL
from annotator.engine.detectors.grounding_dino import DEFAULT_THRESHOLD as DINO_DEFAULT_THRESHOLD
from annotator.engine.detectors.grounding_dino import GroundingDinoEngine
from annotator.engine.detectors.yolo_world import DEFAULT_MODEL as YOLO_DEFAULT_MODEL
from annotator.engine.detectors.yolo_world import DEFAULT_THRESHOLD as YOLO_DEFAULT_THRESHOLD
from annotator.engine.detectors.yolo_world import YoloWorldEngine
from annotator.engine.gemini.client import DEFAULT_MODEL as GEMINI_DEFAULT_MODEL
from annotator.engine.gemini.client import GeminiEngine
from annotator.engine.ollama.client import DEFAULT_MODEL as OLLAMA_DEFAULT_MODEL
from annotator.engine.ollama.client import OllamaEngine

MIN_CONFIDENCE, MAX_CONFIDENCE = 0.05, 0.95


class UnknownEngineError(ValueError):
    pass


@dataclass(frozen=True)
class EngineInfo:
    label: str
    defaults: dict
    build: Callable[[dict, Settings], object]
    supports_refine: bool = True   # VLMs can review their boxes; detectors can't


ENGINES: dict[str, EngineInfo] = {
    "gemini": EngineInfo(
        label="Gemini",
        defaults={"model": GEMINI_DEFAULT_MODEL, "extra": ""},
        build=lambda opts, s: GeminiEngine(opts["model"], api_key=s.gemini_api_key, base_url=s.gemini_base_url),
        supports_refine=GeminiEngine.supports_refine,
    ),
    "claude": EngineInfo(
        label=ClaudeCliEngine.label,
        defaults={"model": CLAUDE_DEFAULT_MODEL, "grid": False, "extra": ""},
        build=lambda opts, s: ClaudeCliEngine(opts["model"], bin=s.claude_bin, grid=opts["grid"]),
        supports_refine=ClaudeCliEngine.supports_refine,
    ),
    "ollama": EngineInfo(
        label=OllamaEngine.label,
        defaults={"model": OLLAMA_DEFAULT_MODEL, "grid": False, "extra": ""},
        build=lambda opts, s: OllamaEngine(opts["model"], url=s.ollama_url, grid=opts["grid"]),
        supports_refine=OllamaEngine.supports_refine,
    ),
    "grounding_dino": EngineInfo(
        label=GroundingDinoEngine.label,
        defaults={"model": DINO_DEFAULT_MODEL, "threshold": DINO_DEFAULT_THRESHOLD},
        build=lambda opts, s: GroundingDinoEngine(opts["model"], opts["threshold"]),
        supports_refine=GroundingDinoEngine.supports_refine,
    ),
    "yolo_world": EngineInfo(
        label=YoloWorldEngine.label,
        defaults={"model": YOLO_DEFAULT_MODEL, "threshold": YOLO_DEFAULT_THRESHOLD},
        build=lambda opts, s: YoloWorldEngine(opts["model"], opts["threshold"]),
        supports_refine=YoloWorldEngine.supports_refine,
    ),
}


def _info(name: str) -> EngineInfo:
    if name not in ENGINES:
        raise UnknownEngineError(name)
    return ENGINES[name]


def _number(value, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return min(MAX_CONFIDENCE, max(MIN_CONFIDENCE, number))


def _clean(value, default):
    if isinstance(default, bool):
        return value if isinstance(value, bool) else default
    if isinstance(default, float):
        return _number(value, default)
    return one_line(str(value or "")) or default


def clean_options(name: str, raw: dict) -> dict:
    """Only the options this engine takes: text as one line, switches only when really true or false, the
    confidence as a number between 0.05 and 0.95 (today's input box). Blanks and unusable values fall back to the
    defaults (extra may be blank)."""
    return {key: _clean(raw.get(key), default) for key, default in _info(name).defaults.items()}


def make_engine(name: str, options: dict, settings: Settings):
    return _info(name).build(clean_options(name, options), settings)
