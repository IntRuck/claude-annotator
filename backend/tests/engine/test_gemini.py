"""Gemini engine, moved from backends.py. Same cases as tests/legacy/test_engines.py, with httpx's MockTransport
instead of patching urllib, and an injected sleep."""
import io
import json

import httpx
import pytest
from PIL import Image

from annotator.engine.base import LimitReached
from annotator.engine.gemini.client import DEFAULT_MODEL, GeminiEngine, retry_delay

BASE = "https://gemini.test/v1beta"


def jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (100, 50)).save(buf, format="JPEG")
    return buf.getvalue()


def reply(objects) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": json.dumps({"objects": objects})}]}}]}


def error(code, err) -> httpx.Response:
    return httpx.Response(code, json={"error": err})


def engine_with(outcomes, model="models/gemini-3.5-flash-lite", key="test-key"):
    """outcomes: dicts (200 JSON), httpx.Response, or exceptions, answered in order. Returns engine, requests, sleeps."""
    requests, sleeps, queue = [], [], list(outcomes)

    def handle(request):
        requests.append(request)
        out = queue.pop(0)
        if isinstance(out, Exception):
            raise out
        return out if isinstance(out, httpx.Response) else httpx.Response(200, json=out)

    engine = GeminiEngine(model, api_key=key, base_url=BASE, transport=httpx.MockTransport(handle), sleep=sleeps.append)
    return engine, requests, sleeps


def test_strips_models_prefix_and_defaults_to_flash_lite():
    assert GeminiEngine("models/gemini-x", api_key="k", base_url=BASE).model == "gemini-x"
    assert GeminiEngine(api_key="k", base_url=BASE).model == DEFAULT_MODEL == "gemini-3.5-flash-lite"


def test_schema_limits_labels_to_class_names():
    schema = GeminiEngine(api_key="k", base_url=BASE)._schema(["can", "bottle"])
    item = schema["properties"]["objects"]["items"]
    assert item["properties"]["label"]["enum"] == ["can", "bottle"]
    assert item["required"] == ["label", "box_2d"]


def test_parse_swaps_y_first_and_skips_unknown_or_bad_boxes():
    text = json.dumps({"objects": [
        {"label": "can", "box_2d": [100, 200, 300, 400]},
        {"label": "pear", "box_2d": [0, 0, 1, 1]},
        {"label": "can", "box_2d": [1, 2, 3]},
    ]})
    boxes, unknown = GeminiEngine._parse(text, ["can"])
    assert boxes == [{"cls": 0, "x1": 0.2, "y1": 0.1, "x2": 0.4, "y2": 0.3}]
    assert unknown == {"pear"}


def test_text_skips_thought_parts_and_errors_without_candidates():
    resp = {"candidates": [{"content": {"parts": [{"text": "thinking", "thought": True}, {"text": "{}"}]}}]}
    assert GeminiEngine._text(resp) == "{}"
    with pytest.raises(RuntimeError, match="SAFETY"):
        GeminiEngine._text({"promptFeedback": {"blockReason": "SAFETY"}})


def test_post_sends_key_header_schema_and_temperature_zero():
    engine, requests, _ = engine_with([{"candidates": []}])
    engine._post("PROMPT", [], ["can"])
    req = requests[0]
    body = json.loads(req.content)
    assert str(req.url) == f"{BASE}/models/gemini-3.5-flash-lite:generateContent"
    assert req.headers["x-goog-api-key"] == "test-key"
    assert body["generationConfig"]["temperature"] == 0
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["contents"][0]["parts"][-1] == {"text": "PROMPT"}


def test_without_a_key_says_where_to_put_it():
    engine, requests, _ = engine_with([], key="  ")
    with pytest.raises(RuntimeError, match="No Gemini API key.*backend/.env"):
        engine._post("p", [], ["can"])
    assert requests == []


def test_per_minute_429_waits_retry_delay_plus_2_then_retries():
    engine, _, sleeps = engine_with([
        error(429, {"message": "quota per minute", "details": [{"retryDelay": "7s"}]}),
        {"ok": True},
    ])
    assert engine._post("p", [], ["can"]) == {"ok": True}
    assert sleeps == [9.0]


def test_per_day_429_is_a_limit():
    engine, _, sleeps = engine_with([error(429, {"message": "x", "details": [{"quotaId": "GenerateRequestsPerDay"}]})])
    with pytest.raises(LimitReached, match="daily free quota"):
        engine._post("p", [], ["can"])
    assert sleeps == []


def test_429_after_three_retries_is_a_limit():
    err = {"message": "slow down", "details": [{"retryDelay": "1s"}]}
    engine, _, sleeps = engine_with([error(429, err) for _ in range(4)])
    with pytest.raises(LimitReached, match="rate limit"):
        engine._post("p", [], ["can"])
    assert sleeps == [3.0, 3.0, 3.0]


def test_402_is_a_limit():
    engine, _, _ = engine_with([error(402, {"message": "pay"})])
    with pytest.raises(LimitReached, match="prepaid credit"):
        engine._post("p", [], ["can"])


def test_503_backs_off_5s_then_10s():
    engine, _, sleeps = engine_with([error(503, {}), error(500, {}), {"ok": 1}])
    assert engine._post("p", [], ["can"]) == {"ok": 1}
    assert sleeps == [5, 10]


def test_404_says_model_not_found():
    engine, _, _ = engine_with([error(404, {"message": "no such model"})])
    with pytest.raises(RuntimeError, match="not found for this key"):
        engine._post("p", [], ["can"])


def test_unreachable_api_says_so():
    engine, _, _ = engine_with([httpx.ConnectError("no route")])
    with pytest.raises(RuntimeError, match="Can't reach the Gemini API"):
        engine._post("p", [], ["can"])


def test_retry_delay_reads_seconds_or_defaults_to_30():
    assert retry_delay({"details": [{"retryDelay": "12s"}]}) == 12.0
    assert retry_delay({}) == 30.0


def test_annotate_end_to_end_with_fake_api():
    engine, requests, _ = engine_with([reply([{"label": "can", "box_2d": [0, 0, 500, 1000]}])])
    image = jpeg()

    boxes, unknown = engine.annotate(image, ["can"], ["can"], [""], "Ignore the top shelf")

    assert boxes == [{"cls": 0, "x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 0.5}]
    assert unknown == set()
    parts = json.loads(requests[0].content)["contents"][0]["parts"]
    assert parts[0]["inline_data"]["mime_type"] == "image/jpeg"
    assert "faint grid" not in parts[-1]["text"]  # Gemini never gets a grid
    assert "Extra instructions: Ignore the top shelf" in parts[-1]["text"]


def test_refine_sends_clean_and_numbered_images_with_the_current_boxes_y_first():
    engine, requests, _ = engine_with([reply([{"label": "can", "box_2d": [100, 200, 300, 400]}])])
    current = [{"class": "can", "box": [200, 100, 400, 300]}]            # x-first, as to_1000 gives them

    boxes, unknown = engine.refine(b"CLEAN", b"OVERLAY", ["can"], ["can"], [""], current, "")

    assert boxes == [{"cls": 0, "x1": 0.2, "y1": 0.1, "x2": 0.4, "y2": 0.3}]
    parts = json.loads(requests[0].content)["contents"][0]["parts"]
    assert [p["inline_data"]["data"] for p in parts[:2]] == ["Q0xFQU4=", "T1ZFUkxBWQ=="]   # base64 of both images
    prompt = parts[-1]["text"]
    assert json.dumps([{"label": "can", "box_2d": [100, 200, 300, 400]}]) in prompt
    assert "numbered #0, #1" in prompt


def test_list_models_keeps_gemini_models_that_can_generate_content(monkeypatch):
    listing = {"models": [
        {"name": "models/gemini-3.5-flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent", "countTokens"]},
        {"name": "models/gemini-3.5-flash-tts", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-embedding-1", "supportedGenerationMethods": ["embedContent"]},
        {"name": "models/gemini-2.0-flash-live", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/imagen-4", "supportedGenerationMethods": ["predict"]},
        {"name": "models/gemma-3", "supportedGenerationMethods": ["generateContent"]},
    ]}
    engine, requests, _ = engine_with([listing])

    assert engine.list_models() == ["gemini-3.5-flash", "gemini-3.5-flash-lite"]
    assert str(requests[0].url) == f"{BASE}/models?pageSize=200"
    assert requests[0].headers["x-goog-api-key"] == "test-key"


def test_list_models_says_why_it_failed():
    engine, _, _ = engine_with([error(403, {"message": "API key not valid"})])
    with pytest.raises(RuntimeError, match="API key not valid"):
        engine.list_models()


def test_engine_flags():
    assert (GeminiEngine.name, GeminiEngine.supports_refine, GeminiEngine.resize_input) == ("gemini", True, True)
