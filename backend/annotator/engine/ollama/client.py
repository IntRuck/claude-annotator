"""Ollama: a local VLM (e.g. qwen3-vl, qwen2.5vl, gemma3), free and offline. Moved from backends.py.

Same request, square image and prompts as today. What changed: httpx instead of urllib (so tests use a MockTransport),
the URL comes from Settings, images arrive as bytes, and an error reply (e.g. a model that isn't pulled) says what
Ollama said instead of "not reachable".
"""
import base64
import io

import httpx
from PIL import Image

from annotator.engine.vlm_prompts import annotate_prompt, parse_objects, refine_prompt

DEFAULT_MODEL = "qwen3-vl:4b"
BAR_NOTE = "\nThe image is padded with grey bars to a square; ignore the bars."


# Local models disagree on coordinates: some answer on a 0-1000 scale (Qwen3-VL), others in pixels (Qwen2.5-VL).
# Sending a 1000x1000 letterboxed image makes the two the same, so either answer maps back correctly.
def letterbox(data: bytes) -> tuple[bytes, tuple[int, int, int, int]]:
    """The photo shrunk into a 1000x1000 grey square, and where it sits: (left, top, width, height)."""
    im = Image.open(io.BytesIO(data)).convert("RGB")
    s = 1000 / max(im.size)
    w, h = round(im.width * s), round(im.height * s)
    canvas = Image.new("RGB", (1000, 1000), (114, 114, 114))
    ox, oy = (1000 - w) // 2, (1000 - h) // 2
    canvas.paste(im.resize((w, h), Image.LANCZOS), (ox, oy))
    out = io.BytesIO()
    canvas.save(out, format="JPEG", quality=92)
    return out.getvalue(), (ox, oy, w, h)


def unbox(boxes: list[dict], geo) -> list[dict]:
    """Boxes on the square (0-1) back to 0-1 of the photo itself."""
    ox, oy, w, h = geo
    return [{**b, "x1": (b["x1"] * 1000 - ox) / w, "x2": (b["x2"] * 1000 - ox) / w,
             "y1": (b["y1"] * 1000 - oy) / h, "y2": (b["y2"] * 1000 - oy) / h} for b in boxes]


class OllamaEngine:
    name = "ollama"
    label = "Ollama"
    supports_refine = True
    resize_input = True

    def __init__(self, model: str = DEFAULT_MODEL, *, url: str, grid: bool = False, timeout: float = 600,
                 transport: httpx.BaseTransport | None = None):
        self.model = (model or DEFAULT_MODEL).strip()
        self.url = url.rstrip("/")
        self.grid = grid
        self.timeout = timeout
        self.transport = transport

    def _chat(self, prompt: str, images: list[bytes]) -> str:
        body = {"model": self.model, "stream": False, "format": "json", "options": {"temperature": 0},
                "messages": [{"role": "user", "content": prompt,
                              "images": [base64.b64encode(i).decode() for i in images]}]}
        try:
            with httpx.Client(transport=self.transport, timeout=self.timeout) as http:
                r = http.post(self.url + "/api/chat", json=body)
        except httpx.TimeoutException:
            raise RuntimeError(f"Ollama didn't answer within {self.timeout:g} s") from None
        except httpx.TransportError as e:
            raise RuntimeError(f"Ollama not reachable at {self.url} ({e}). Is 'ollama serve' running "
                               f"and is the model pulled ('ollama pull {self.model}')?") from e
        try:
            data = r.json()
        except ValueError:
            data = {}
        if "error" in data:
            raise RuntimeError("Ollama: " + str(data["error"]))
        if not r.is_success:
            raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text[:200]}")
        return (data.get("message") or {}).get("content", "")

    def list_models(self) -> list[str]:
        """The models pulled into Ollama. Raises RuntimeError when Ollama isn't running."""
        try:
            with httpx.Client(transport=self.transport, timeout=2) as http:
                r = http.get(self.url + "/api/tags")
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama isn't running at {self.url} ({e})") from e
        return [m["name"] for m in r.json().get("models", [])]

    def annotate(self, image: bytes, classes, prompts, descs, extra):
        square, geo = letterbox(image)
        note = extra + BAR_NOTE if extra else BAR_NOTE.strip()
        text = self._chat(annotate_prompt("", classes, prompts, note, self.grid, descs), [square])
        boxes, unknown = parse_objects(text, classes, (1000, 1000))
        return unbox(boxes, geo), unknown

    def refine(self, clean: bytes, overlay: bytes, classes, prompts, descs, current, extra):
        square_clean, geo = letterbox(clean)
        square_overlay, _ = letterbox(overlay)
        ox, oy, w, h = geo
        cur = [{"class": c["class"], "box": [round(ox + c["box"][0] / 1000 * w), round(oy + c["box"][1] / 1000 * h),
                                              round(ox + c["box"][2] / 1000 * w), round(oy + c["box"][3] / 1000 * h)]}
               for c in current]
        text = self._chat(refine_prompt("", classes, prompts, cur, extra, descs), [square_clean, square_overlay])
        boxes, unknown = parse_objects(text, classes, (1000, 1000))
        return unbox(boxes, geo), unknown
