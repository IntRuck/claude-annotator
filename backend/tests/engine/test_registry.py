"""Engine registry: which engines exist, the options each one takes, and building one for a job."""
import pytest

from annotator.config.settings import Settings
from annotator.engine.gemini.client import GeminiEngine
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
