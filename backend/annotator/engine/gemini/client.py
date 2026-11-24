"""Gemini (Google AI Studio API key; free tier if no billing is linked). Moved from backends.py.

Same behaviour as today; what changed: httpx instead of urllib (so tests use a MockTransport), the key and URL
come from Settings, `sleep` is injectable, and images arrive as bytes instead of file paths.
"""
import base64
import json
import re
import time
from collections.abc import Callable

import httpx

from annotator.engine.base import LimitReached
from annotator.engine.vlm_prompts import RULES, annotate_prompt, refine_prompt

DEFAULT_MODEL = "gemini-3.5-flash-lite"

# Gemini is trained to answer boxes as box_2d = [ymin, xmin, ymax, xmax] on 0-1000.
# We ask for its native format (y first!) and swap to x-first when parsing.
GEMINI_RULES = RULES.replace(
    "- Coordinates are integers on a 0-1000 scale relative to image width and height: "
    "[x1, y1, x2, y2], x from left to right, y from top to bottom.",
    "- box_2d is [ymin, xmin, ymax, xmax]: integers normalized to 0-1000 relative to image "
    "height (y) and width (x). y comes first.")
GEMINI_OUTPUT = """Reply with JSON: {"objects": [{"label": "<class name>", "box_2d": [ymin, xmin, ymax, xmax]}]}
If nothing matches, reply {"objects": []}"""


def retry_delay(err: dict) -> float:
    for d in err.get("details", []) or []:
        rd = d.get("retryDelay")
        if rd:
            try:
                return float(str(rd).rstrip("s"))
            except ValueError:
                pass
    return 30.0


class GeminiEngine:
    name = "gemini"
    label = "Gemini"
    supports_refine = True
    resize_input = True    # send a copy of at most 1568 px; Gemini has native box training, so no grid

    def __init__(self, model: str = DEFAULT_MODEL, *, api_key: str, base_url: str, timeout: float = 180,
                 transport: httpx.BaseTransport | None = None, sleep: Callable[[float], None] = time.sleep):
        self.model = (model or DEFAULT_MODEL).strip().removeprefix("models/")
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport
        self.sleep = sleep

    def _schema(self, classes):
        return {"type": "OBJECT", "properties": {"objects": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {"label": {"type": "STRING", "enum": list(classes)},   # only your class names
                           "box_2d": {"type": "ARRAY", "items": {"type": "INTEGER"}}},
            "required": ["label", "box_2d"]}}},
            "required": ["objects"]}

    def _post(self, prompt: str, images: list[bytes], classes) -> dict:
        if not self.api_key:
            raise RuntimeError("No Gemini API key. Put GEMINI_API_KEY=... in backend/.env (see README), "
                               "then restart the worker.")
        parts = [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(img).decode()}}
                 for img in images]
        parts.append({"text": prompt})
        body = {"contents": [{"parts": parts}],
                "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                                     "responseSchema": self._schema(classes)}}
        url = f"{self.base_url}/models/{self.model}:generateContent"
        with httpx.Client(transport=self.transport, timeout=self.timeout) as http:
            for attempt in range(4):
                try:
                    r = http.post(url, json=body, headers={"x-goog-api-key": self.api_key})
                except httpx.TransportError as e:
                    raise RuntimeError(f"Can't reach the Gemini API ({e}). Check your internet connection.") from e
                if r.is_success:
                    return r.json()
                try:
                    err = r.json().get("error", {})
                except ValueError:
                    err = {}
                msg = err.get("message", f"HTTP {r.status_code}")
                if r.status_code == 429:
                    details = json.dumps(err.get("details", []))
                    if "PerDay" in details or "per day" in msg.lower():
                        raise LimitReached(f"Gemini daily free quota used up for {self.model}. "
                                           f"It resets tomorrow; or switch to another model. ({msg[:150]})")
                    wait = retry_delay(err) + 2           # per-minute limit: wait and try again
                    if attempt < 3 and wait <= 90:
                        self.sleep(wait)
                        continue
                    raise LimitReached(f"Gemini rate limit: {msg[:200]}")
                if r.status_code == 402:
                    raise LimitReached("Gemini prepaid credit is empty (this key is on a paid project).")
                if r.status_code in (500, 503) and attempt < 3:
                    self.sleep(5 * (attempt + 1))           # model overloaded: back off a bit
                    continue
                if r.status_code == 404:
                    raise RuntimeError(f"Gemini model '{self.model}' not found for this key. Pick one from "
                                       f"the list in the app. ({msg[:150]})")
                raise RuntimeError(f"Gemini HTTP {r.status_code}: {msg[:300]}")
        raise RuntimeError("Gemini: too many retries")

    def list_models(self) -> list[str]:
        """Gemini models this key can use for generateContent (today's filter). Raises RuntimeError with the reason."""
        try:
            with httpx.Client(transport=self.transport, timeout=10) as http:
                r = http.get(f"{self.base_url}/models", params={"pageSize": 200},
                             headers={"x-goog-api-key": self.api_key})
        except httpx.TransportError as e:
            raise RuntimeError(f"Can't reach the Gemini API ({e})") from e
        if not r.is_success:
            try:
                msg = r.json().get("error", {}).get("message", "")
            except ValueError:
                msg = ""
            raise RuntimeError(msg or f"HTTP {r.status_code}")
        return sorted(m["name"].removeprefix("models/") for m in r.json().get("models", [])
                      if "generateContent" in m.get("supportedGenerationMethods", [])
                      and "gemini" in m.get("name", "")
                      and not any(x in m["name"] for x in ("tts", "image", "embedding", "live", "audio")))

    @staticmethod
    def _text(resp):
        cands = resp.get("candidates") or []
        if not cands:
            reason = (resp.get("promptFeedback") or {}).get("blockReason", "no answer")
            raise RuntimeError(f"Gemini returned no result ({reason})")
        parts = (cands[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))

    @staticmethod
    def _parse(text, classes):
        """box_2d is [ymin, xmin, ymax, xmax] on 0-1000 -> our x-first normalized boxes."""
        m = re.search(r"\{.*\}|\[.*\]", text, re.S)
        if not m:
            raise ValueError("No JSON in Gemini reply: " + text[:200])
        data = json.loads(m.group(0))
        objs = data.get("objects", []) if isinstance(data, dict) else data
        lower = {c.lower(): i for i, c in enumerate(classes)}
        boxes, unknown = [], set()
        for o in objs:
            name = str(o.get("label", o.get("class", ""))).strip()
            idx = lower.get(name.lower())
            b = o.get("box_2d") or []
            if idx is None:
                unknown.add(name)
                continue
            if len(b) != 4:
                continue
            ymin, xmin, ymax, xmax = [float(v) for v in b]
            boxes.append({"cls": idx, "x1": xmin / 1000, "y1": ymin / 1000, "x2": xmax / 1000, "y2": ymax / 1000})
        return boxes, unknown

    def annotate(self, image: bytes, classes, prompts, descs, extra):
        prompt = annotate_prompt("", classes, prompts, extra, False, descs, GEMINI_RULES, GEMINI_OUTPUT)
        return self._parse(self._text(self._post(prompt, [image], classes)), classes)

    def refine(self, clean: bytes, overlay: bytes, classes, prompts, descs, current, extra):
        # current comes in x-first; show it to Gemini in its own y-first format
        cur = [{"label": c["class"], "box_2d": [c["box"][1], c["box"][0], c["box"][3], c["box"][2]]} for c in current]
        prompt = refine_prompt("", classes, prompts, cur, extra, descs, GEMINI_RULES, GEMINI_OUTPUT)
        return self._parse(self._text(self._post(prompt, [clean, overlay], classes)), classes)
