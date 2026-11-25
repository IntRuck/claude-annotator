"""Claude CLI engine, moved from backends.py. Same cases as tests/legacy/test_engines.py; a fake process runner stands
in for subprocess.run, and images arrive as bytes, written to a temporary folder Claude may read."""
import io
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from annotator.engine.base import LimitReached
from annotator.engine.claude_cli.client import DEFAULT_MODEL, ClaudeCliEngine, claude_path

CAN = ["can"]


def jpeg(color=(0, 0, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 20), color).save(buf, format="JPEG")
    return buf.getvalue()


def runner(stdout="", stderr="", returncode=0, raises=None):
    """A fake subprocess.run. Records the command, its keyword arguments and the files in its folder at call time."""
    seen = []

    def run(cmd, **kw):
        folder = Path(kw["cwd"])
        seen.append({"cmd": cmd, "kw": kw, "folder": folder,
                     "files": {p.name: p.read_bytes() for p in folder.iterdir()}})
        if raises:
            raise raises
        return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)

    return run, seen


def answer(result, is_error=False) -> str:
    return json.dumps({"result": result, "is_error": is_error})


def engine(run, **kw) -> ClaudeCliEngine:
    return ClaudeCliEngine(kw.pop("model", "haiku"), bin="claude-test", run=run, **kw)


def test_builds_todays_command_and_never_passes_an_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-leak")
    run, seen = runner(stdout=answer('{"objects": []}'))

    engine(run, timeout=99).annotate(jpeg(), CAN, CAN, [""], "")

    call = seen[0]
    prompt = call["cmd"][2]
    assert call["cmd"] == ["claude-test", "-p", prompt, "--output-format", "json", "--allowedTools", "Read",
                           "--max-turns", "6", "--add-dir", str(call["folder"]), "--model", "haiku"]
    assert call["kw"]["cwd"] == str(call["folder"])
    assert call["kw"]["timeout"] == 99
    assert "ANTHROPIC_API_KEY" not in call["kw"]["env"]       # runs on the Claude plan login, never a paid key


def test_annotate_puts_the_image_where_claude_can_read_it_names_it_in_the_prompt_and_cleans_up():
    run, seen = runner(stdout=answer('{"objects": []}'))
    image = jpeg((200, 0, 0))

    assert engine(run).annotate(image, CAN, CAN, [""], "") == ([], set())

    call = seen[0]
    assert call["files"] == {"image.jpg": image}
    assert call["cmd"][2].startswith("Use the Read tool to open the image file: image.jpg\n")
    assert not call["folder"].exists()


def test_annotate_turns_the_reply_into_boxes():
    run, _ = runner(stdout=answer('Here you go: {"objects": [{"class": "can", "box": [0, 0, 500, 1000]}, '
                                  '{"class": "pear", "box": [1, 1, 2, 2]}]}'))
    boxes, unknown = engine(run).annotate(jpeg(), CAN, CAN, [""], "")
    assert boxes == [{"cls": 0, "x1": 0.0, "y1": 0.0, "x2": 0.5, "y2": 1.0}]
    assert unknown == {"pear"}


def test_the_prompt_mentions_the_grid_only_when_one_is_drawn():
    run, seen = runner(stdout=answer('{"objects": []}'))
    engine(run, grid=True).annotate(jpeg(), CAN, CAN, [""], "")
    engine(run, grid=False).annotate(jpeg(), CAN, CAN, [""], "")
    assert "faint grid every 100 units" in seen[0]["cmd"][2]
    assert "grid" not in seen[1]["cmd"][2]


def test_refine_sends_both_images_in_order_with_the_current_boxes():
    run, seen = runner(stdout=answer('{"objects": []}'))
    clean, overlay = jpeg((0, 0, 0)), jpeg((255, 255, 255))
    current = [{"class": "can", "box": [100, 100, 500, 500]}]

    engine(run).refine(clean, overlay, CAN, CAN, [""], current, "")

    call = seen[0]
    assert call["files"] == {"original.jpg": clean, "boxes.jpg": overlay}
    assert call["cmd"][2].startswith("Use the Read tool to open two images:\n1. original.jpg\n2. boxes.jpg\n")
    assert '[{"class": "can", "box": [100, 100, 500, 500]}]' in call["cmd"][2]


@pytest.mark.parametrize("message", ["You've hit your usage limit", "5-hour limit reached", "Weekly limit",
                                     "rate limit"])
def test_limit_text_is_a_usage_limit(message):
    run, _ = runner(stdout=answer(message, is_error=True))
    with pytest.raises(LimitReached):
        engine(run).annotate(jpeg(), CAN, CAN, [""], "")


def test_limit_text_on_stderr_is_a_usage_limit_too():
    run, _ = runner(stdout="", stderr="Claude AI usage limit reached|1700000000", returncode=1)
    with pytest.raises(LimitReached):
        engine(run).annotate(jpeg(), CAN, CAN, [""], "")


def test_an_error_without_an_answer_says_what_claude_printed():
    run, _ = runner(stdout="", stderr="boom", returncode=1)
    with pytest.raises(RuntimeError, match="boom"):
        engine(run).annotate(jpeg(), CAN, CAN, [""], "")


def test_a_slow_answer_says_how_long_it_waited_instead_of_dumping_the_command():
    run, _ = runner(raises=subprocess.TimeoutExpired(["claude-test", "-p", "a very long prompt"], 99))
    with pytest.raises(RuntimeError, match="didn't answer within 99 s") as caught:
        engine(run, timeout=99).annotate(jpeg(), CAN, CAN, [""], "")
    assert "very long prompt" not in str(caught.value)


def test_a_missing_cli_says_how_to_fix_it():
    run, _ = runner(raises=FileNotFoundError(2, "No such file"))
    with pytest.raises(RuntimeError, match="Claude CLI not found"):
        engine(run).annotate(jpeg(), CAN, CAN, [""], "")


def test_the_default_model_is_sonnet():
    assert DEFAULT_MODEL == ClaudeCliEngine(bin="claude").model == "sonnet"


def test_engine_flags():
    assert (ClaudeCliEngine.name, ClaudeCliEngine.supports_refine, ClaudeCliEngine.resize_input) == (
        "claude", True, True)


# ---------- finding the CLI (today's find_claude + availability) ----------
def which_finds(*present):
    return lambda name: f"C:/bin/{name}" if name in present else None


def test_claude_path_prefers_claude_bin_when_it_exists():
    assert claude_path("/opt/claude", which=lambda name: name) == "/opt/claude"


def test_a_claude_bin_that_does_not_exist_is_not_found():
    assert claude_path("/opt/missing", which=which_finds("claude")) is None


def test_claude_path_looks_on_the_path_for_claude_then_claude_cmd():
    assert claude_path("", which=which_finds("claude", "claude.cmd")) == "C:/bin/claude"
    assert claude_path("", which=which_finds("claude.cmd")) == "C:/bin/claude.cmd"
    assert claude_path("", which=which_finds()) is None
