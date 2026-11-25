"""Claude through the Claude Code CLI on your Claude plan login (no API key). Moved from backends.py.

Same command, prompts and limit check as today. What changed: images arrive as bytes and are written to a temporary
folder that Claude may read (removed afterwards), the process runner is injectable for tests, and a timeout or a
missing CLI gives a short reason instead of the whole command line.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from annotator.engine.base import LimitReached
from annotator.engine.vlm_prompts import annotate_prompt, parse_objects, refine_prompt

DEFAULT_MODEL = "sonnet"
LIMIT_PAT = re.compile(r"(usage limit|limit reached|5-hour limit|weekly limit|rate limit)", re.I)
NOT_FOUND = ("Claude CLI not found. Install Claude Code and log in once (run claude), or set CLAUDE_BIN in the "
             "backend's env file to its full path, then restart the worker.")


def claude_path(configured: str = "", which: Callable[[str], str | None] = shutil.which) -> str | None:
    """Where the claude CLI is: CLAUDE_BIN when set, else claude or claude.cmd on the PATH. None when not found."""
    configured = (configured or "").strip()
    if configured:
        return which(configured)
    return which("claude") or which("claude.cmd")


class ClaudeCliEngine:
    name = "claude"
    label = "Claude"
    supports_refine = True
    resize_input = True

    def __init__(self, model: str = DEFAULT_MODEL, *, bin: str = "", grid: bool = False, timeout: float = 300,
                 run: Callable = subprocess.run):
        self.model = (model or DEFAULT_MODEL).strip()
        self.bin = bin
        self.grid = grid
        self.timeout = timeout
        self.run = run

    def _call(self, prompt: str, folder: Path) -> str:
        executable = claude_path(self.bin) or self.bin.strip() or "claude"
        cmd = [executable, "-p", prompt, "--output-format", "json",
               "--allowedTools", "Read", "--max-turns", "6", "--add-dir", str(folder)]
        if self.model:
            cmd += ["--model", self.model]
        # Not reading a key: the child gets a copy of the environment without ANTHROPIC_API_KEY, so the CLI uses
        # the Claude plan login and never a paid API key.
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        try:
            proc = self.run(cmd, cwd=str(folder), capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=self.timeout, env=env)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Claude CLI didn't answer within {self.timeout:g} s") from None
        except FileNotFoundError:
            raise RuntimeError(NOT_FOUND) from None
        out, err = (proc.stdout or "").strip(), (proc.stderr or "").strip()
        text, is_error = out, proc.returncode != 0
        try:
            data = json.loads(out)
            text = data.get("result") or ""
            is_error = is_error or bool(data.get("is_error"))
        except (ValueError, AttributeError):
            pass
        if LIMIT_PAT.search(text) or LIMIT_PAT.search(err):
            raise LimitReached((text or err)[:300])
        if is_error and not text:
            raise RuntimeError((err or out or "claude exited with an error")[:500])
        return text

    def _ask(self, prompt: str, images: dict[str, bytes]) -> str:
        """Write `images` (file name -> bytes) to a fresh folder, ask Claude, and remove the folder again."""
        with tempfile.TemporaryDirectory(prefix="annotator-claude-") as tmp:
            folder = Path(tmp)
            for file_name, data in images.items():
                (folder / file_name).write_bytes(data)
            return self._call(prompt, folder)

    def annotate(self, image: bytes, classes, prompts, descs, extra):
        ref = "Use the Read tool to open the image file: image.jpg\n"
        text = self._ask(annotate_prompt(ref, classes, prompts, extra, self.grid, descs), {"image.jpg": image})
        return parse_objects(text, classes)

    def refine(self, clean: bytes, overlay: bytes, classes, prompts, descs, current, extra):
        ref = "Use the Read tool to open two images:\n1. original.jpg\n2. boxes.jpg\n"
        text = self._ask(refine_prompt(ref, classes, prompts, current, extra, descs),
                         {"original.jpg": clean, "boxes.jpg": overlay})
        return parse_objects(text, classes)
