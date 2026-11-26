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


def test_ids_with_status_by_name(db_session, pid):
    repo = ImageRepository(db_session)
    rows = {n: add(repo, pid, n) for n in ("c.jpg", "a.jpg", "b.jpg")}
    rows["b.jpg"].status = "error"
    repo.save(rows["b.jpg"])

    assert repo.ids_with_status(pid, ["unlabeled"]) == [rows["a.jpg"].id, rows["c.jpg"].id]
    assert repo.ids_with_status(pid, None) == [rows["a.jpg"].id, rows["b.jpg"].id, rows["c.jpg"].id]


def test_summary_by_project_counts_per_project(db_session, pid):
    repo = ImageRepository(db_session)
    other = ProjectRepository(db_session).create("Other").id
    first = add(repo, pid, "b.jpg")
    second = add(repo, pid, "a.jpg")
    add(repo, other, "x.jpg")
    second.status, second.flagged = "edited", True
    repo.save(second)

    summary = repo.summary_by_project()
    assert summary[pid]["all"] == 2
    assert (summary[pid]["unlabeled"], summary[pid]["edited"], summary[pid]["flagged"]) == (1, 1, 1)
    assert summary[pid]["cover_image_id"] == first.id
    assert summary[pid]["last_changed_at"] == second.updated_at
    assert summary[other]["all"] == 1


def test_file_paths_lists_originals_and_thumbnails(db_session, pid):
    repo = ImageRepository(db_session)
    add(repo, pid, "a.jpg")
    assert sorted(repo.file_paths(pid)) == [f"{pid}/a.jpg", f"{pid}/thumbs/a.jpg"]
