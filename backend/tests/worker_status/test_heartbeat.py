"""The worker's heartbeat: what each engine can do right now, sent every few seconds."""
import threading
import time

import pytest

from annotator.config.settings import Settings
from annotator.worker_status.heartbeat import Heartbeat, Probes, cached_for, engine_availability


def settings(key="") -> Settings:
    return Settings(_env_file=None, gemini_api_key=key, ollama_url="http://127.0.0.1:11434")


def fails(message):
    def probe(*_):
        raise RuntimeError(message)
    return probe


def probes(**kw) -> Probes:
    """Everything installed and running unless a test says otherwise; `asked` records which checks ran."""
    asked = []

    def record(name, answer):
        def probe(*args):
            asked.append(name)
            return answer(*args) if callable(answer) else answer
        return probe

    p = Probes(gemini_models=record("gemini", kw.get("gemini_models", ["gemini-a"])),
               ollama_models=record("ollama", kw.get("ollama_models", ["qwen3-vl:4b"])),
               claude_path=record("claude", kw.get("claude_path", "C:/bin/claude.exe")),
               installed=record("installed", kw.get("installed", lambda *modules: True)),
               cuda=record("cuda", kw.get("cuda", True)))
    p.asked = asked
    return p


def availability(key="k", **kw):
    p = probes(**kw)
    return engine_availability(settings(key), p), p.asked


def test_every_engine_is_checked():
    engines, _ = availability()
    assert list(engines) == ["gemini", "claude", "ollama", "grounding_dino", "yolo_world"]
    assert all(e["ready"] for e in engines.values())


# ---------- Gemini ----------
def test_without_a_gemini_key_gemini_is_not_ready_and_says_where_the_key_goes():
    engines, asked = availability(key="")
    assert engines["gemini"]["ready"] is False
    assert "GEMINI_API_KEY" in engines["gemini"]["note"]
    assert engines["gemini"]["models"] == []
    assert "gemini" not in asked                         # no call to Google without a key


def test_with_a_key_gemini_is_ready_with_the_models_the_key_can_use():
    engines, _ = availability(gemini_models=["gemini-a", "gemini-b"])
    assert engines["gemini"] == {"ready": True, "note": "", "models": ["gemini-a", "gemini-b"]}


def test_a_failed_model_list_keeps_gemini_ready_with_a_note():
    engines, _ = availability(gemini_models=fails("Can't reach the Gemini API"))
    assert engines["gemini"]["ready"] is True
    assert engines["gemini"]["models"] == []
    assert engines["gemini"]["note"] == "Couldn't list Gemini models: Can't reach the Gemini API"


# ---------- Claude CLI ----------
def test_claude_is_ready_when_the_cli_is_found():
    engines, _ = availability()
    assert engines["claude"] == {"ready": True, "note": "", "models": []}


def test_without_the_cli_claude_is_not_ready_and_says_how_to_get_it():
    engines, _ = availability(claude_path=None)
    assert engines["claude"]["ready"] is False
    assert "Claude CLI not found" in engines["claude"]["note"]
    assert "CLAUDE_BIN" in engines["claude"]["note"]


# ---------- Ollama ----------
def test_ollama_is_ready_with_the_models_pulled_into_it():
    engines, _ = availability(ollama_models=["qwen3-vl:4b", "gemma3:4b"])
    assert engines["ollama"] == {"ready": True, "note": "", "models": ["qwen3-vl:4b", "gemma3:4b"]}


def test_ollama_not_running_says_where_it_looked_and_how_to_start_it():
    engines, _ = availability(ollama_models=fails("refused"))
    assert engines["ollama"]["ready"] is False
    assert engines["ollama"]["note"] == ("Ollama isn't running at http://127.0.0.1:11434. Start it (ollama serve) "
                                         "and pull a model (ollama pull qwen3-vl:4b).")


def test_ollama_without_models_is_not_ready_and_says_which_to_pull():
    engines, _ = availability(ollama_models=[])
    assert engines["ollama"]["ready"] is False
    assert engines["ollama"]["note"] == "Ollama has no models yet. Pull one: ollama pull qwen3-vl:4b"


# ---------- detectors ----------
def test_detectors_need_their_packages():
    engines, _ = availability(installed=lambda *modules: "ultralytics" in modules)
    assert engines["grounding_dino"]["ready"] is False
    assert "pip install" in engines["grounding_dino"]["note"]
    assert engines["yolo_world"]["ready"] is True


@pytest.mark.parametrize("engine", ["grounding_dino", "yolo_world"])
def test_a_detector_without_a_gpu_still_runs_but_warns_it_is_slow(engine):
    engines, _ = availability(cuda=False)
    assert engines[engine] == {"ready": True, "note": "No CUDA GPU found: it runs on the CPU (slow).", "models": []}


def test_the_gpu_is_not_checked_when_no_detector_is_installed():
    _, asked = availability(installed=lambda *modules: False)
    assert "cuda" not in asked                           # checking means importing torch, which takes seconds


# ---------- asking Google for the model list less often than the heartbeat ----------
def test_cached_for_keeps_an_answer_until_it_is_old():
    now, calls = [0.0], []
    models = cached_for(600, lambda: calls.append(1) or ["gemini-a"], clock=lambda: now[0])
    assert models() == ["gemini-a"]
    now[0] = 599
    assert models() == ["gemini-a"]
    assert len(calls) == 1
    now[0] = 600
    models()
    assert len(calls) == 2


def test_cached_for_asks_again_after_a_failure():
    answers = [RuntimeError("offline"), ["gemini-a"]]

    def ask():
        out = answers.pop(0)
        if isinstance(out, Exception):
            raise out
        return out

    models = cached_for(600, ask, clock=lambda: 0.0)
    with pytest.raises(RuntimeError):
        models()
    assert models() == ["gemini-a"]


def test_heartbeat_beats_repeatedly_checks_engines_less_often_and_says_goodbye_on_stop():
    beats, checks, gone = [], [], threading.Event()
    heartbeat = Heartbeat(beat=beats.append, gone=gone.set,
                          availability=lambda: checks.append(1) or {"gemini": {"ready": True}},
                          every=0.01, refresh_every=60)
    heartbeat.start()
    deadline = time.monotonic() + 5
    while len(beats) < 3 and time.monotonic() < deadline:
        time.sleep(0.01)
    heartbeat.stop()

    assert len(beats) >= 3
    assert beats[0] == {"gemini": {"ready": True}}
    assert len(checks) == 1
    assert gone.is_set()


def test_a_failed_beat_does_not_stop_the_heartbeat():
    beats = []

    def beat(engines):
        beats.append(engines)
        if len(beats) == 1:
            raise RuntimeError("database down")

    heartbeat = Heartbeat(beat=beat, gone=lambda: None, availability=lambda: {}, every=0.01)
    heartbeat.start()
    deadline = time.monotonic() + 5
    while len(beats) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    heartbeat.stop()
    assert len(beats) >= 2
