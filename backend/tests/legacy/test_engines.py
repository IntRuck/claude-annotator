"""backends.py engines: Gemini, Claude CLI, Ollama, detector helpers, registry."""
import io
import json
import urllib.error
from types import SimpleNamespace

import pytest

import backends as b


# ======================= Gemini =======================
class _Resp:
    def __init__(self, data):
        self._data = json.dumps(data).encode()

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(code, error):
    return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(json.dumps({"error": error}).encode()))


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    sleeps = []
    monkeypatch.setattr(b.time, "sleep", sleeps.append)
    return b.GeminiBackend("models/gemini-3.5-flash-lite"), sleeps


def _queue_urlopen(monkeypatch, outcomes):
    calls = []

    def fake(req, timeout=None):
        calls.append(req)
        out = outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return _Resp(out)

    monkeypatch.setattr(b.urllib.request, "urlopen", fake)
    return calls


def test_gemini_strips_models_prefix():
    assert b.GeminiBackend("models/gemini-x").model == "gemini-x"


def test_gemini_schema_limits_labels_to_class_names():
    schema = b.GeminiBackend()._schema(["can", "bottle"])
    item = schema["properties"]["objects"]["items"]
    assert item["properties"]["label"]["enum"] == ["can", "bottle"]
    assert item["required"] == ["label", "box_2d"]


def test_gemini_parse_swaps_y_first_and_skips_unknown_or_bad_boxes():
    text = json.dumps({"objects": [
        {"label": "can", "box_2d": [100, 200, 300, 400]},
        {"label": "pear", "box_2d": [0, 0, 1, 1]},
        {"label": "can", "box_2d": [1, 2, 3]},
    ]})
    boxes, unknown = b.GeminiBackend._parse(text, ["can"])
    assert boxes == [{"cls": 0, "x1": 0.2, "y1": 0.1, "x2": 0.4, "y2": 0.3}]
    assert unknown == {"pear"}


def test_gemini_text_skips_thought_parts_and_errors_without_candidates():
    resp = {"candidates": [{"content": {"parts": [{"text": "thinking", "thought": True}, {"text": "{}"}]}}]}
    assert b.GeminiBackend._text(resp) == "{}"
    with pytest.raises(RuntimeError, match="SAFETY"):
        b.GeminiBackend._text({"promptFeedback": {"blockReason": "SAFETY"}})


def test_gemini_post_sends_key_header_schema_and_temperature_zero(gemini, monkeypatch):
    backend, _ = gemini
    calls = _queue_urlopen(monkeypatch, [{"candidates": []}])
    backend._post("PROMPT", [], ["can"])
    req = calls[0]
    body = json.loads(req.data)
    assert req.full_url.endswith("/models/gemini-3.5-flash-lite:generateContent")
    assert req.get_header("X-goog-api-key") == "test-key"
    assert body["generationConfig"]["temperature"] == 0
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["contents"][0]["parts"][-1] == {"text": "PROMPT"}


def test_gemini_without_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="No Gemini API key"):
        b.GeminiBackend()._post("p", [], ["can"])


def test_gemini_per_minute_429_waits_retry_delay_plus_2_then_retries(gemini, monkeypatch):
    backend, sleeps = gemini
    _queue_urlopen(monkeypatch, [
        _http_error(429, {"message": "quota per minute", "details": [{"retryDelay": "7s"}]}),
        {"ok": True},
    ])
    assert backend._post("p", [], ["can"]) == {"ok": True}
    assert sleeps == [9.0]


def test_gemini_per_day_429_is_a_limit(gemini, monkeypatch):
    backend, sleeps = gemini
    _queue_urlopen(monkeypatch, [_http_error(429, {"message": "x", "details": [{"quotaId": "GenerateRequestsPerDay"}]})])
    with pytest.raises(b.LimitReached, match="daily free quota"):
        backend._post("p", [], ["can"])
    assert sleeps == []


def test_gemini_429_after_three_retries_is_a_limit(gemini, monkeypatch):
    backend, sleeps = gemini
    err = {"message": "slow down", "details": [{"retryDelay": "1s"}]}
    _queue_urlopen(monkeypatch, [_http_error(429, err) for _ in range(4)])
    with pytest.raises(b.LimitReached, match="rate limit"):
        backend._post("p", [], ["can"])
    assert sleeps == [3.0, 3.0, 3.0]


def test_gemini_402_is_a_limit(gemini, monkeypatch):
    backend, _ = gemini
    _queue_urlopen(monkeypatch, [_http_error(402, {"message": "pay"})])
    with pytest.raises(b.LimitReached, match="prepaid credit"):
        backend._post("p", [], ["can"])


def test_gemini_503_backs_off_5s_then_10s(gemini, monkeypatch):
    backend, sleeps = gemini
    _queue_urlopen(monkeypatch, [_http_error(503, {}), _http_error(500, {}), {"ok": 1}])
    assert backend._post("p", [], ["can"]) == {"ok": 1}
    assert sleeps == [5, 10]


def test_gemini_404_says_model_not_found(gemini, monkeypatch):
    backend, _ = gemini
    _queue_urlopen(monkeypatch, [_http_error(404, {"message": "no such model"})])
    with pytest.raises(RuntimeError, match="not found for this key"):
        backend._post("p", [], ["can"])


def test_retry_delay_reads_seconds_or_defaults_to_30():
    assert b._retry_delay({"details": [{"retryDelay": "12s"}]}) == 12.0
    assert b._retry_delay({}) == 30.0


def test_gemini_annotate_end_to_end_with_fake_api(gemini, monkeypatch, make_image, tmp_path):
    backend, _ = gemini
    img = make_image(tmp_path / "x.jpg")
    reply = {"candidates": [{"content": {"parts": [{"text": json.dumps({"objects": [{"label": "can", "box_2d": [0, 0, 500, 1000]}]})}]}}]}
    calls = _queue_urlopen(monkeypatch, [reply])
    boxes, unknown = backend.annotate(img, ["can"], ["can"], "", True)
    assert boxes == [{"cls": 0, "x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 0.5}]
    assert "faint grid" not in json.loads(calls[0].data)["contents"][0]["parts"][-1]["text"]  # Gemini never gets a grid


def test_gemini_backend_flags():
    g = b.GeminiBackend
    assert (g.supports_refine, g.uses_grid, g.resize_input) == (True, False, True)


# ======================= Claude CLI =======================
@pytest.fixture
def claude_run(monkeypatch):
    monkeypatch.setenv("CLAUDE_BIN", "claude-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-leak")
    seen = {}

    def run_with(stdout="", stderr="", returncode=0):
        def fake(cmd, **kw):
            seen["cmd"], seen["kw"] = cmd, kw
            return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)

        monkeypatch.setattr(b.subprocess, "run", fake)
        return seen

    return run_with


def test_claude_call_builds_the_command_and_drops_the_api_key(claude_run, tmp_path):
    seen = claude_run(stdout=json.dumps({"result": "ANSWER", "is_error": False}))
    text = b.ClaudeBackend("haiku", timeout=99)._call("PROMPT", tmp_path)
    assert text == "ANSWER"
    assert seen["cmd"] == [
        "claude-test", "-p", "PROMPT", "--output-format", "json", "--allowedTools", "Read",
        "--max-turns", "6", "--add-dir", str(tmp_path), "--model", "haiku",
    ]
    assert seen["kw"]["cwd"] == str(tmp_path)
    assert seen["kw"]["timeout"] == 99
    assert "ANTHROPIC_API_KEY" not in seen["kw"]["env"]


@pytest.mark.parametrize("message", ["You've hit your usage limit", "5-hour limit reached", "Weekly limit", "rate limit"])
def test_claude_limit_text_raises_limit_reached(claude_run, tmp_path, message):
    claude_run(stdout=json.dumps({"result": message, "is_error": True}))
    with pytest.raises(b.LimitReached):
        b.ClaudeBackend()._call("p", tmp_path)


def test_claude_error_without_text_raises_with_stderr(claude_run, tmp_path):
    claude_run(stdout="", stderr="boom", returncode=1)
    with pytest.raises(RuntimeError, match="boom"):
        b.ClaudeBackend()._call("p", tmp_path)


def test_claude_annotate_passes_image_name_and_folder(monkeypatch, tmp_path):
    seen = {}

    def fake_call(self, prompt, workdir):
        seen["prompt"], seen["workdir"] = prompt, workdir
        return '{"objects": []}'

    monkeypatch.setattr(b.ClaudeBackend, "_call", fake_call)
    img = tmp_path / "shot__in.jpg"
    assert b.ClaudeBackend().annotate(img, ["can"], ["can"], "", False) == ([], set())
    assert seen["prompt"].startswith("Use the Read tool to open the image file: shot__in.jpg\n")
    assert seen["workdir"] == tmp_path


def test_find_claude_prefers_env(monkeypatch):
    monkeypatch.setenv("CLAUDE_BIN", "/opt/claude")
    assert b.find_claude() == "/opt/claude"


# ======================= Ollama =======================
def test_ollama_letterbox_pads_to_1000_square_and_unbox_maps_back(make_image, tmp_path):
    src = make_image(tmp_path / "wide.jpg", size=(200, 100))
    out, geo = b.OllamaBackend._letterbox(src)
    assert geo == (0, 250, 1000, 500)
    from PIL import Image

    assert Image.open(out).size == (1000, 1000)
    boxes = b.OllamaBackend._unbox([{"cls": 0, "x1": 0.0, "y1": 0.25, "x2": 0.5, "y2": 0.5}], geo)
    assert boxes == [{"cls": 0, "x1": 0.0, "y1": 0.0, "x2": 0.5, "y2": 0.5}]


def test_ollama_annotate_adds_bar_note_and_returns_real_image_coordinates(monkeypatch, make_image, tmp_path):
    src = make_image(tmp_path / "wide.jpg", size=(200, 100))
    seen = {}

    def fake_chat(self, prompt, paths):
        seen["prompt"], seen["paths"] = prompt, paths
        return '{"objects": [{"class": "can", "box": [0, 250, 500, 500]}]}'

    monkeypatch.setattr(b.OllamaBackend, "_chat", fake_chat)
    boxes, _ = b.OllamaBackend().annotate(src, ["can"], ["can"], "", False)
    assert boxes == [{"cls": 0, "x1": 0.0, "y1": 0.0, "x2": 0.5, "y2": 0.5}]
    assert "padded with grey bars" in seen["prompt"]
    assert seen["paths"][0].name == "wide__lb.jpg"


def test_ollama_chat_request_shape(monkeypatch, tmp_path, make_image):
    img = make_image(tmp_path / "x.jpg")
    calls = _queue_urlopen(monkeypatch, [{"message": {"content": "{}"}}])
    assert b.OllamaBackend("qwen3-vl:4b", "http://h:1/")._chat("P", [img]) == "{}"
    body = json.loads(calls[0].data)
    assert calls[0].full_url == "http://h:1/api/chat"
    assert (body["model"], body["stream"], body["format"], body["options"]) == ("qwen3-vl:4b", False, "json", {"temperature": 0})
    assert len(body["messages"][0]["images"]) == 1


def test_ollama_error_reply_raises(monkeypatch, tmp_path):
    _queue_urlopen(monkeypatch, [{"error": "model not found"}])
    with pytest.raises(RuntimeError, match="Ollama: model not found"):
        b.OllamaBackend()._chat("P", [])


# ======================= detectors (no torch needed) =======================
def test_match_class_exact_then_longest_substring_overlap_else_none():
    prompts = ["red tin can", "can", "spray bottle"]
    assert b._match_class("Can", prompts) == 1
    assert b._match_class("red tin can lid", prompts) == 0
    assert b._match_class("banana", prompts) is None


def test_detector_backends_cannot_refine_and_use_original_images():
    for cls in (b.GroundingDinoBackend, b.YoloWorldBackend):
        assert (cls.supports_refine, cls.uses_grid, cls.resize_input) == (False, False, False)


# ======================= registry =======================
def test_make_backend_picks_engine_and_defaults():
    assert isinstance(b.make_backend("unknown", {}), b.ClaudeBackend)
    assert b.make_backend("claude", {}).model == "sonnet"
    assert b.make_backend("gemini", {}).model == "gemini-3.5-flash-lite"
    o = b.make_backend("ollama", {})
    assert (o.model, o.url) == ("qwen3-vl:4b", "http://127.0.0.1:11434")
    g = b.make_backend("grounding_dino", {})
    assert (g.model_id, g.threshold) == ("IDEA-Research/grounding-dino-tiny", 0.35)
    y = b.make_backend("yolo_world", {"threshold": 0.5})
    assert (y.weights, y.threshold) == ("yolov8s-worldv2.pt", 0.5)
