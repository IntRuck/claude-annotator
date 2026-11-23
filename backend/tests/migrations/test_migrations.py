"""Flyway guard, like backend_web's FlywayMigrationImmutabilityTest.

`db/migration/applied.sha256` lists every migration already applied somewhere, in `sha256sum` format
(`<sha256>  V1__name.sql`). An applied file must never change: add a new version instead.
"""
import hashlib
from pathlib import Path

from tests.migrations.checks import check_migrations

MIGRATIONS = Path(__file__).resolve().parents[2] / "db" / "migration"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _write(folder: Path, files: dict[str, str], applied: dict[str, str] | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (folder / name).write_text(body, encoding="utf-8")
    lines = [f"{sha}  {name}" for name, sha in (applied or {}).items()]
    (folder / "applied.sha256").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return folder


def test_real_migration_folder_has_no_problems():
    assert check_migrations(MIGRATIONS) == []


def test_unchanged_applied_migration_is_fine(tmp_path):
    folder = _write(tmp_path, {"V1__projects.sql": "create table p();"}, {"V1__projects.sql": _sha("create table p();")})
    assert check_migrations(folder) == []


def test_changed_applied_migration_is_reported(tmp_path):
    folder = _write(tmp_path, {"V1__projects.sql": "create table p(id int);"}, {"V1__projects.sql": _sha("create table p();")})
    assert check_migrations(folder) == [
        "V1__projects.sql was changed after it was applied; add a new version instead"
    ]


def test_applied_migration_that_was_deleted_is_reported(tmp_path):
    folder = _write(tmp_path, {}, {"V1__projects.sql": _sha("x")})
    assert check_migrations(folder) == ["V1__projects.sql is listed as applied but the file is missing"]


def test_gap_in_versions_is_reported(tmp_path):
    folder = _write(tmp_path, {"V1__a.sql": "", "V3__c.sql": ""})
    assert check_migrations(folder) == ["versions must go 1, 2, 3 ... without gaps; found 1, 3"]


def test_duplicate_version_is_reported(tmp_path):
    folder = _write(tmp_path, {"V1__a.sql": "", "V1__b.sql": ""})
    assert check_migrations(folder) == ["version 1 is used by more than one file: V1__a.sql, V1__b.sql"]


def test_badly_named_sql_file_is_reported(tmp_path):
    folder = _write(tmp_path, {"V1__a.sql": "", "v2_Bad Name.sql": ""})
    assert check_migrations(folder) == [
        "v2_Bad Name.sql does not match V<number>__<snake_case>.sql"
    ]
