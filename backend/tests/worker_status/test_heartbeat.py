"""The worker's heartbeat: what each engine can do right now, sent every few seconds."""
import threading
import time

from annotator.config.settings import Settings
from annotator.worker_status.heartbeat import Heartbeat, engine_availability


def settings(key="") -> Settings:
    return Settings(_env_file=None, gemini_api_key=key)


def test_without_a_gemini_key_gemini_is_not_ready_and_says_where_the_key_goes():
    calls = []
    engines = engine_availability(settings(), list_gemini_models=lambda: calls.append(1) or [])
    assert engines["gemini"]["ready"] is False
    assert "GEMINI_API_KEY" in engines["gemini"]["note"]
    assert engines["gemini"]["models"] == []
    assert calls == []                                   # no call to Google without a key


def test_with_a_key_gemini_is_ready_with_the_models_the_key_can_use():
    engines = engine_availability(settings("k"), list_gemini_models=lambda: ["gemini-a", "gemini-b"])
    assert engines["gemini"] == {"ready": True, "note": "", "models": ["gemini-a", "gemini-b"]}


def test_a_failed_model_list_keeps_gemini_ready_with_a_note():
    def boom():
        raise RuntimeError("Can't reach the Gemini API")

    engines = engine_availability(settings("k"), list_gemini_models=boom)
    assert engines["gemini"]["ready"] is True
    assert engines["gemini"]["models"] == []
    assert engines["gemini"]["note"] == "Couldn't list Gemini models: Can't reach the Gemini API"


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
