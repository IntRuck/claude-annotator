import pytest
from sqlalchemy.exc import IntegrityError

from annotator.activity.repository import ActivityRepository
from annotator.project.repository import ProjectRepository

pytestmark = pytest.mark.db


def test_recent_entries_newest_first_limited_to_the_project(db_session):
    projects = ProjectRepository(db_session)
    pid, other = projects.create("P").id, projects.create("Other").id
    repo = ActivityRepository(db_session)
    for n in range(3):
        repo.add(pid, f"line {n}")
    repo.add(other, "elsewhere")

    recent = repo.list_recent(pid, limit=2)

    assert [e.message for e in recent] == ["line 2", "line 1"]
    assert (recent[0].level, recent[0].job_id, recent[0].image_id) == ("info", None, None)
    assert recent[0].created_at is not None


def test_database_refuses_an_unknown_level(db_session):
    pid = ProjectRepository(db_session).create("P").id
    with pytest.raises(IntegrityError):
        ActivityRepository(db_session).add(pid, "x", level="panic")
