import pytest
from sqlalchemy.exc import IntegrityError

from annotator.classes.models import ProjectClass
from annotator.classes.repository import ClassNameTakenError, ClassRepository
from annotator.project.repository import ProjectRepository

pytestmark = pytest.mark.db


@pytest.fixture
def ids(db_session):
    projects = ProjectRepository(db_session)
    return projects.create("A").id, projects.create("B").id


def test_indexes_count_up_per_project(db_session, ids):
    a, b = ids
    repo = ClassRepository(db_session)
    assert [repo.add(a, n, "", "").class_index for n in ("can", "bottle", "jar")] == [0, 1, 2]
    assert repo.add(b, "can", "", "").class_index == 0
    assert [c.name for c in repo.list_for_project(a)] == ["can", "bottle", "jar"]


def test_find_by_name_ignores_capitals(db_session, ids):
    repo = ClassRepository(db_session)
    repo.add(ids[0], "Tin_Can", "metal", "silver")
    found = repo.find_by_name(ids[0], "tin_can")
    assert (found.class_index, found.detector_prompt, found.description) == (0, "metal", "silver")
    assert repo.find_by_name(ids[1], "tin_can") is None


def test_duplicate_name_ignoring_capitals_raises_and_the_session_stays_usable(db_session, ids):
    repo = ClassRepository(db_session)
    repo.add(ids[0], "can", "", "")
    with pytest.raises(ClassNameTakenError):
        repo.add(ids[0], "CAN", "", "")
    assert repo.add(ids[0], "bottle", "", "").class_index == 1


def test_rename_to_a_taken_name_raises(db_session, ids):
    repo = ClassRepository(db_session)
    repo.add(ids[0], "can", "", "")
    bottle = repo.add(ids[0], "bottle", "", "")
    bottle.name = "Can"
    with pytest.raises(ClassNameTakenError):
        repo.save(bottle)


def test_rename_keeps_the_index(db_session, ids):
    repo = ClassRepository(db_session)
    repo.add(ids[0], "can", "", "")
    row = repo.get(ids[0], 0)
    row.name = "tin_can"
    repo.save(row)
    db_session.expire_all()
    assert repo.get(ids[0], 0).name == "tin_can"


def test_database_refuses_names_with_spaces(db_session, ids):
    db_session.add(ProjectClass(project_id=ids[0], class_index=0, name="tin can", detector_prompt="", description=""))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_deleting_a_project_deletes_its_classes(db_session, ids):
    repo = ClassRepository(db_session)
    repo.add(ids[0], "can", "", "")
    db_session.delete(ProjectRepository(db_session).get(ids[0]))
    db_session.flush()
    db_session.expire_all()
    assert repo.list_for_project(ids[0]) == []


def test_count_by_project(db_session, ids):
    a, b = ids
    repo = ClassRepository(db_session)
    for n in ("can", "bottle"):
        repo.add(a, n, "", "")
    counts = repo.count_by_project()
    assert counts[a] == 2
    assert b not in counts
