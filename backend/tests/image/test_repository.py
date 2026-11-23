import pytest
from sqlalchemy.exc import IntegrityError

from annotator.image.repository import ImageRepository
from annotator.project.repository import ProjectRepository

pytestmark = pytest.mark.db


@pytest.fixture
def pid(db_session):
    return ProjectRepository(db_session).create("P").id


def add(repo, pid, name):
    return repo.add(pid, file_name=name, stem=name.rsplit(".", 1)[0], storage_path=f"{pid}/{name}",
                    thumb_path=f"{pid}/thumbs/{name}", width=100, height=50)


def test_new_rows_start_unlabeled_and_unflagged(db_session, pid):
    row = add(ImageRepository(db_session), pid, "a.jpg")
    assert (row.status, row.flagged, row.box_count, row.note) == ("unlabeled", False, 0, "")
    assert row.id > 0 and row.updated_at is not None


def test_list_sorted_by_name_and_filtered(db_session, pid):
    repo = ImageRepository(db_session)
    for n in ("c.jpg", "a.jpg", "b.jpg"):
        add(repo, pid, n)
    b = repo.find_by_names(pid, ["b.jpg"])[0]
    b.status, b.flagged = "reviewed", True
    db_session.flush()

    assert [i.file_name for i in repo.list_for_project(pid, "all")] == ["a.jpg", "b.jpg", "c.jpg"]
    assert [i.file_name for i in repo.list_for_project(pid, "reviewed")] == ["b.jpg"]
    assert [i.file_name for i in repo.list_for_project(pid, "flagged")] == ["b.jpg"]
    assert [i.file_name for i in repo.list_for_project(pid, "unlabeled")] == ["a.jpg", "c.jpg"]
    assert repo.counts(pid) == {"all": 3, "unlabeled": 2, "auto": 0, "edited": 0, "reviewed": 1, "flagged": 1, "error": 0}


def test_find_by_names_returns_only_existing_names(db_session, pid):
    repo = ImageRepository(db_session)
    add(repo, pid, "a.jpg")
    assert [i.file_name for i in repo.find_by_names(pid, ["a.jpg", "zzz.jpg"])] == ["a.jpg"]


def test_same_file_name_twice_in_a_project_is_refused(db_session, pid):
    repo = ImageRepository(db_session)
    add(repo, pid, "a.jpg")
    with pytest.raises(IntegrityError):
        add(repo, pid, "a.jpg")


def test_unknown_status_is_refused(db_session, pid):
    row = add(ImageRepository(db_session), pid, "a.jpg")
    row.status = "done"
    with pytest.raises(IntegrityError):
        db_session.flush()
