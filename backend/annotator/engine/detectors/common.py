"""What the open-vocabulary detectors share (moved from backends.py).

Heavy libraries (torch, transformers, ultralytics) are imported only when a detector runs, so the worker starts
without them. Install them with the `detectors` extra.
"""
import importlib.util
import sys
from collections.abc import Callable
from functools import cache


def installed(*modules: str) -> bool:
    """Are these packages installed? Looks without importing them (importing torch takes seconds)."""
    return all(importlib.util.find_spec(m) is not None for m in modules)


@cache
def cuda_available() -> bool:
    """Is there a CUDA GPU for torch? Checked once per process: the first import of torch is slow."""
    if not installed("torch"):
        return False
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def free_gpu() -> None:
    torch = sys.modules.get("torch")      # only if a detector already loaded it
    if torch is not None and torch.cuda.is_available():
        torch.cuda.empty_cache()


class ModelCache:
    """Only one detector model stays loaded, so a 4 GB GPU doesn't run out of memory (today's _get_cached)."""

    def __init__(self, free: Callable[[], None] = free_gpu):
        self.key = None
        self.obj = None
        self.free = free

    def get(self, key, loader: Callable[[], object]):
        if self.key != key:
            if self.key is not None:
                self.key, self.obj = None, None
                self.free()
            self.obj = loader()
            self.key = key
        return self.obj


MODELS = ModelCache()   # shared by both detectors in the worker process


def match_class(label: str, prompts: list[str]) -> int | None:
    """Map a detector's text label back to a class position: exact match, else the longest overlapping prompt."""
    label = (label or "").strip().lower()
    low = [p.lower() for p in prompts]
    if label in low:
        return low.index(label)
    best, best_len = None, 0
    for i, p in enumerate(low):
        if p in label or label in p:
            overlap = min(len(p), len(label))
            if overlap > best_len:
                best, best_len = i, overlap
    return best
