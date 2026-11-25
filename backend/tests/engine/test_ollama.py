"""Ollama engine (a local VLM), moved from backends.py. Same cases as tests/legacy/test_engines.py, with httpx's
MockTransport instead of patching urllib; images arrive as bytes."""
import base64
import io
import json

import httpx
import pytest
from PIL import Image

from annotator.engine.ollama.client import DEFAULT_MODEL, OllamaEngine, letterbox, unbox

URL = "http://h:1/"
CAN = ["can"]


def jpeg(size=(200, 100)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (0, 0, 0)).save(buf, format="JPEG")
    return buf.getvalue()


def chat(content: str) -> dict:
    return {"model": "qwen3-vl:4b", "message": {"role": "assistant", "content": content}, "done": True}


def ollama_with(outcomes, model="qwen3-vl:4b", **kw):
    """outcomes: dicts (200 JSON), httpx.Response, or exceptions, answered in order. Returns the engine and requests."""
    requests, queue = [], list(outcomes)

    def handle(request):
        requests.append(request)
        out = queue.pop(0)
        if isinstance(out, Exception):
            raise out
        return out if isinstance(out, httpx.Response) else httpx.Response(200, json=out)

    return OllamaEngine(model, url=URL, transport=httpx.MockTransport(handle), **kw), requests


def sent(request) -> dict:
    return json.loads(request.content)


def sent_images(request) -> list[Image.Image]:
    return [Image.open(io.BytesIO(base64.b64decode(i))) for i in sent(request)["messages"][0]["images"]]


# ---------- the square: local models answer on 0-1000 or in pixels; a 1000x1000 image makes both the same ----------
def test_letterbox_pads_to_a_1000_square_with_grey_bars_and_unbox_maps_back():
    data, geo = letterbox(jpeg((200, 100)))
    square = Image.open(io.BytesIO(data)).convert("RGB")
    assert geo == (0, 250, 1000, 500)
    assert square.size == (1000, 1000)
    assert all(abs(c - 114) <= 3 for c in square.getpixel((500, 100)))      # the bar above the photo
    assert unbox([{"cls": 0, "x1": 0.0, "y1": 0.25, "x2": 0.5, "y2": 0.5}], geo) == [
        {"cls": 0, "x1": 0.0, "y1": 0.0, "x2": 0.5, "y2": 0.5}]


def test_annotate_sends_the_square_with_a_note_about_the_bars_and_returns_real_image_coordinates():
    engine, requests = ollama_with([chat('{"objects": [{"class": "can", "box": [0, 250, 500, 500]}]}')])

    boxes, unknown = engine.annotate(jpeg((200, 100)), CAN, CAN, [""], "")

    assert boxes == [{"cls": 0, "x1": 0.0, "y1": 0.0, "x2": 0.5, "y2": 0.5}]
    assert unknown == set()
    assert "The image is padded with grey bars to a square; ignore the bars." in sent(requests[0])["messages"][0]["content"]
    assert [i.size for i in sent_images(requests[0])] == [(1000, 1000)]


def test_extra_instructions_come_first_then_the_bar_note():
    engine, requests = ollama_with([chat('{"objects": []}')])
    engine.annotate(jpeg(), CAN, CAN, [""], "top shelf only")
    assert ("Extra instructions: top shelf only\nThe image is padded with grey bars"
            in sent(requests[0])["messages"][0]["content"])


def test_the_prompt_mentions_the_grid_only_when_one_is_drawn():
    with_grid, r1 = ollama_with([chat('{"objects": []}')], grid=True)
    without, r2 = ollama_with([chat('{"objects": []}')])
    with_grid.annotate(jpeg(), CAN, CAN, [""], "")
    without.annotate(jpeg(), CAN, CAN, [""], "")
    assert "faint grid every 100 units" in sent(r1[0])["messages"][0]["content"]
    assert "grid" not in sent(r2[0])["messages"][0]["content"]


def test_chat_request_shape():
    engine, requests = ollama_with([chat('{"objects": []}')])
    engine.annotate(jpeg(), CAN, CAN, [""], "")
    body = sent(requests[0])
    assert str(requests[0].url) == "http://h:1/api/chat"
    assert (body["model"], body["stream"], body["format"], body["options"]) == (
        "qwen3-vl:4b", False, "json", {"temperature": 0})


def test_refine_moves_the_current_boxes_into_the_square_and_sends_both_images():
    engine, requests = ollama_with([chat('{"objects": [{"class": "can", "box": [0, 250, 1000, 750]}]}')])
    current = [{"class": "can", "box": [0, 0, 1000, 1000]}]

    boxes, _ = engine.refine(jpeg((200, 100)), jpeg((200, 100)), CAN, CAN, [""], current, "")

    assert '[{"class": "can", "box": [0, 250, 1000, 750]}]' in sent(requests[0])["messages"][0]["content"]
    assert [i.size for i in sent_images(requests[0])] == [(1000, 1000), (1000, 1000)]
    assert boxes == [{"cls": 0, "x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0}]


# ---------- errors ----------
def test_an_error_reply_says_what_ollama_said():
    engine, _ = ollama_with([httpx.Response(404, json={"error": "model 'qwen9' not found"})])
    with pytest.raises(RuntimeError, match="Ollama: model 'qwen9' not found"):
        engine.annotate(jpeg(), CAN, CAN, [""], "")


def test_ollama_not_running_says_how_to_start_it():
    engine, _ = ollama_with([httpx.ConnectError("refused")])
    with pytest.raises(RuntimeError, match=r"Ollama not reachable at http://h:1.*ollama pull qwen3-vl:4b"):
        engine.annotate(jpeg(), CAN, CAN, [""], "")


def test_a_slow_answer_says_how_long_it_waited():
    engine, _ = ollama_with([httpx.ReadTimeout("timed out")], timeout=600)
    with pytest.raises(RuntimeError, match="didn't answer within 600 s"):
        engine.annotate(jpeg(), CAN, CAN, [""], "")


# ---------- installed models (today's ollama_status) ----------
def test_list_models_names_the_installed_models():
    engine, requests = ollama_with([{"models": [{"name": "qwen3-vl:4b"}, {"name": "gemma3:4b"}]}])
    assert engine.list_models() == ["qwen3-vl:4b", "gemma3:4b"]
    assert str(requests[0].url) == "http://h:1/api/tags"


def test_list_models_says_when_ollama_is_not_running():
    engine, _ = ollama_with([httpx.ConnectError("refused")])
    with pytest.raises(RuntimeError, match="Ollama isn't running at http://h:1"):
        engine.list_models()


def test_defaults_and_flags():
    assert DEFAULT_MODEL == OllamaEngine(url=URL).model == "qwen3-vl:4b"
    assert (OllamaEngine.name, OllamaEngine.supports_refine, OllamaEngine.resize_input) == ("ollama", True, True)
