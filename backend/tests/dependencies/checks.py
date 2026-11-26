"""Compares pyproject.toml with requirements.lock. The `detectors` extra isn't locked: PyTorch has to match your CUDA
version, so it's installed by hand (see the README)."""
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

LOCKED_EXTRAS = ("dev",)


def _needed(pyproject: Path) -> list[Requirement]:
    project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
    extras = project.get("optional-dependencies", {})
    lines = project.get("dependencies", []) + [line for extra in LOCKED_EXTRAS for line in extras.get(extra, [])]
    return [Requirement(line) for line in lines]


def _pinned(lock: Path) -> dict[str, Version]:
    pinned = {}
    for line in lock.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        req = Requirement(line)
        (spec,) = req.specifier
        pinned[canonicalize_name(req.name)] = Version(spec.version)
    return pinned


def check_lock(backend: Path) -> list[str]:
    lock = backend / "requirements.lock"
    if not lock.exists():
        return ["requirements.lock is missing; create it with the command in backend/CLAUDE.md"]
    pinned = _pinned(lock)
    problems = []
    for req in _needed(backend / "pyproject.toml"):
        version = pinned.get(canonicalize_name(req.name))
        if version is None:
            problems.append(f"{req.name} is in pyproject.toml but not in requirements.lock; re-run the lock command")
        elif version not in req.specifier:
            problems.append(f"{req.name} {version} in requirements.lock doesn't meet {req.specifier} in pyproject.toml; "
                            "re-run the lock command")
    return problems
