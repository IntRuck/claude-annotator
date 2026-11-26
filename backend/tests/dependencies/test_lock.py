"""Lock-file guard, like the Flyway guard in tests/migrations.

`requirements.lock` pins the exact version of every library the backend installs (the web has package-lock.json).
pyproject.toml says what we need (`fastapi>=0.115`); the lock says which versions were tested (`fastapi==0.165.0`).
Adding a library to pyproject.toml without re-running the lock command is reported here.
"""
from pathlib import Path

from tests.dependencies.checks import check_lock

BACKEND = Path(__file__).resolve().parents[2]


def _write(folder: Path, pyproject: str, lock: str | None) -> Path:
    (folder / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    if lock is not None:
        (folder / "requirements.lock").write_text(lock, encoding="utf-8")
    return folder


PYPROJECT = """
[project]
name = "annotator"
dependencies = ["fastapi>=0.115", "uvicorn[standard]>=0.32"]

[project.optional-dependencies]
detectors = ["ultralytics>=8.3"]
dev = ["pytest>=8.3"]
"""


def test_real_lock_matches_pyproject():
    assert check_lock(BACKEND) == []


def test_lock_with_every_dependency_pinned_is_fine(tmp_path):
    folder = _write(tmp_path, PYPROJECT, "fastapi==0.165.0\n    # via annotator\nuvicorn==0.54.0\npytest==9.2.0\n")
    assert check_lock(folder) == []


def test_missing_lock_is_reported(tmp_path):
    folder = _write(tmp_path, PYPROJECT, None)
    assert check_lock(folder) == ["requirements.lock is missing; create it with the command in backend/CLAUDE.md"]


def test_dependency_missing_from_lock_is_reported(tmp_path):
    folder = _write(tmp_path, PYPROJECT, "fastapi==0.165.0\nuvicorn==0.54.0\n")
    assert check_lock(folder) == ["pytest is in pyproject.toml but not in requirements.lock; re-run the lock command"]


def test_locked_version_below_the_minimum_is_reported(tmp_path):
    folder = _write(tmp_path, PYPROJECT, "fastapi==0.100.0\nuvicorn==0.54.0\npytest==9.2.0\n")
    assert check_lock(folder) == [
        "fastapi 0.100.0 in requirements.lock doesn't meet >=0.115 in pyproject.toml; re-run the lock command"
    ]


def test_names_are_compared_the_way_pip_compares_them(tmp_path):
    pyproject = '[project]\nname = "a"\ndependencies = ["Pydantic_Settings>=2.6"]\n'
    folder = _write(tmp_path, pyproject, "pydantic-settings==2.16.3 ; python_full_version >= '3.12'\n")
    assert check_lock(folder) == []
