import pytest
from sqlalchemy.exc import IntegrityError

from annotator.project.repository import ProjectRepository

pytestmark = pytest.mark.db


def test_create_gets_an_id_and_created_at(db_session):
    project = ProjectRepository(db_session).create("Shelf")
    assert project.id > 0
    assert project.created_at is not None


def test_list_is_newest_first_and_get_finds_by_id(db_session):
    repo = ProjectRepository(db_session)
    first, second = repo.create("First"), repo.create("Second")
    assert [p.name for p in repo.list()][:2] == ["Second", "First"]
    assert repo.get(first.id).name == "First"
    assert repo.get(second.id + 1000) is None


def test_database_refuses_a_blank_name(db_session):
    with pytest.raises(IntegrityError):
        ProjectRepository(db_session).create("   ")
