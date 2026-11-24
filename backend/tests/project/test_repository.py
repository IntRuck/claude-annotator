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


def test_deleting_a_project_removes_its_classes_images_and_boxes(db_session):
    """The project owns everything under it. Boxes also point at their class, which mustn't block the delete."""
    from sqlalchemy import text

    pid = ProjectRepository(db_session).create("Gone").id
    db_session.execute(text("insert into classes (project_id, class_index, name) values (:p, 0, 'can')"), {"p": pid})
    image_id = db_session.execute(text(
        "insert into images (project_id, file_name, stem, storage_path, thumb_path, width, height) "
        "values (:p, 'a.jpg', 'a', 's', 't', 10, 10) returning id"), {"p": pid}).scalar_one()
    db_session.execute(text("insert into boxes (image_id, project_id, class_index, x1, y1, x2, y2, source) "
                            "values (:i, :p, 0, 0.1, 0.1, 0.5, 0.5, 'ai')"), {"i": image_id, "p": pid})

    db_session.execute(text("delete from projects where id = :p"), {"p": pid})

    left = db_session.execute(text(
        "select (select count(*) from classes where project_id = :p) + (select count(*) from images where project_id = :p)"
        " + (select count(*) from boxes where project_id = :p)"), {"p": pid}).scalar_one()
    assert left == 0
