"""Engine registry: which engines exist, the options each one takes, and building one for a job."""
import pytest

from annotator.config.settings import Settings
from annotator.engine.claude_cli.client import ClaudeCliEngine
from annotator.engine.detectors.grounding_dino import GroundingDinoEngine
from annotator.engine.detectors.yolo_world import YoloWorldEngine
from annotator.engine.gemini.client import GeminiEngine
from annotator.engine.ollama.client import OllamaEngine
from annotator.engine.registry import ENGINES, UnknownEngineError, clean_options, make_engine


def settings(**kw) -> Settings:
    return Settings(_env_file=None, gemini_api_key="k", gemini_base_url="https://gemini.test/v1beta", **kw)


def test_gemini_is_registered_with_a_label_and_can_refine():
    assert ENGINES["gemini"].label == "Gemini"
    assert ENGINES["gemini"].supports_refine is True


def test_options_keep_only_what_the_engine_takes_trimmed_with_defaults():
    assert clean_options("gemini", {"model": " gemini-x ", "extra": "  Ignore the top shelf ", "junk": 1}) == {
        "model": "gemini-x", "extra": "Ignore the top shelf"}
    assert clean_options("gemini", {}) == {"model": "gemini-3.5-flash-lite", "extra": ""}


def test_extra_instructions_become_one_line():
    assert clean_options("gemini", {"extra": "line one\nline two"})["extra"] == "line one line two"


def test_unknown_engine_is_refused():
    with pytest.raises(UnknownEngineError):
        clean_options("robot", {})
    with pytest.raises(UnknownEngineError):
        make_engine("robot", {}, settings())


def test_make_engine_builds_gemini_with_the_key_and_url_from_settings():
    engine = make_engine("gemini", {"model": "gemini-x", "extra": ""}, settings())
    assert isinstance(engine, GeminiEngine)
    assert (engine.model, engine.api_key, engine.base_url) == ("gemini-x", "k", "https://gemini.test/v1beta")


# ---------- Claude CLI ----------
def test_claude_defaults_to_sonnet_without_a_grid():
    assert clean_options("claude", {}) == {"model": "sonnet", "grid": False, "extra": ""}


def test_a_switch_is_on_only_when_it_is_true():
    assert clean_options("claude", {"grid": True})["grid"] is True
    assert clean_options("claude", {"grid": False})["grid"] is False
    assert clean_options("claude", {"grid": "yes"})["grid"] is False     # not a JSON true: the default


def test_make_engine_builds_claude_with_its_model_grid_and_the_cli_from_settings():
    engine = make_engine("claude", {"model": "haiku", "grid": True}, settings(claude_bin="C:/bin/claude.exe"))
    assert isinstance(engine, ClaudeCliEngine)
    assert (engine.model, engine.grid, engine.bin) == ("haiku", True, "C:/bin/claude.exe")
    assert ENGINES["claude"].label == "Claude"
    assert ENGINES["claude"].supports_refine is True


# ---------- Ollama ----------
def test_ollama_defaults_to_qwen3_vl_without_a_grid():
    assert clean_options("ollama", {}) == {"model": "qwen3-vl:4b", "grid": False, "extra": ""}


def test_make_engine_builds_ollama_with_its_model_grid_and_the_url_from_settings():
    engine = make_engine("ollama", {"model": "gemma3:4b", "grid": True}, settings(ollama_url="http://gpu-box:11434/"))
    assert isinstance(engine, OllamaEngine)
    assert (engine.model, engine.grid, engine.url) == ("gemma3:4b", True, "http://gpu-box:11434")
    assert ENGINES["ollama"].supports_refine is True


# ---------- detectors ----------
def test_detectors_take_a_model_and_a_confidence_but_no_extra_instructions():
    assert clean_options("grounding_dino", {"extra": "x"}) == {"model": "IDEA-Research/grounding-dino-tiny",
                                                               "threshold": 0.35}
    assert clean_options("yolo_world", {}) == {"model": "yolov8s-worldv2.pt", "threshold": 0.25}


@pytest.mark.parametrize(("given", "kept"), [
    (0.5, 0.5), ("0.4", 0.4), (2, 0.95), (0, 0.05),                 # kept between 5 % and 95 % like today's box
    ("abc", 0.35), (True, 0.35), (float("nan"), 0.35), (None, 0.35),  # not a number: the default
])
def test_the_confidence_is_a_number_kept_between_5_and_95_percent(given, kept):
    assert clean_options("grounding_dino", {"threshold": given})["threshold"] == kept


def test_make_engine_builds_the_detectors_with_their_model_and_confidence():
    dino = make_engine("grounding_dino", {"model": "IDEA-Research/grounding-dino-base", "threshold": 0.5}, settings())
    yolo = make_engine("yolo_world", {"model": "yoloe-11s-seg.pt", "threshold": 0.3}, settings())
    assert isinstance(dino, GroundingDinoEngine)
    assert (dino.model, dino.threshold) == ("IDEA-Research/grounding-dino-base", 0.5)
    assert isinstance(yolo, YoloWorldEngine)
    assert (yolo.model, yolo.threshold) == ("yoloe-11s-seg.pt", 0.3)
    assert (ENGINES["grounding_dino"].label, ENGINES["yolo_world"].label) == ("Grounding DINO", "YOLO-World")
    assert ENGINES["grounding_dino"].supports_refine is ENGINES["yolo_world"].supports_refine is False
