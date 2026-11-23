"""Checks for the Flyway migration folder (test utility, used by test_migrations.py)."""
import hashlib
import re
from collections import defaultdict
from pathlib import Path

NAME = re.compile(r"^V(\d+)__[a-z0-9]+(?:_[a-z0-9]+)*\.sql$")


def _applied(folder: Path) -> dict[str, str]:
    applied = {}
    path = folder / "applied.sha256"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                sha, name = line.split(maxsplit=1)
                applied[name.strip().lstrip("*")] = sha
    return applied


def check_migrations(folder: Path) -> list[str]:
    problems = []
    files = sorted(p.name for p in folder.glob("*.sql"))

    by_version = defaultdict(list)
    for name in files:
        m = NAME.match(name)
        if not m:
            problems.append(f"{name} does not match V<number>__<snake_case>.sql")
            continue
        by_version[int(m.group(1))].append(name)

    for version, names in sorted(by_version.items()):
        if len(names) > 1:
            problems.append(f"version {version} is used by more than one file: {', '.join(names)}")

    versions = sorted(by_version)
    if versions and versions != list(range(1, len(versions) + 1)):
        problems.append(f"versions must go 1, 2, 3 ... without gaps; found {', '.join(map(str, versions))}")

    for name, sha in _applied(folder).items():
        path = folder / name
        if not path.exists():
            problems.append(f"{name} is listed as applied but the file is missing")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            problems.append(f"{name} was changed after it was applied; add a new version instead")

    return problems
