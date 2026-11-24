import io

import pytest
from PIL import Image

from annotator.common.problem import ApiError
from annotator.image.service import ImageService, UploadedFile
from annotator.project.service import ProjectService
from annotator.storage.storage_service import StorageError
from tests.fakes import FakeImageRepository, FakeProjectRepository, FakeStorage


def jpg(size=(100, 50)):
    buf = io.BytesIO()
    Image.new("RGB", size, (90, 90, 90)).save(buf, format="JPEG")
    return buf.getvalue()


def upload(name, data=None):
    return UploadedFile(file_name=name, content=jpg() if data is None else data, content_type="image/jpeg")


@pytest.fixture
def storage():
    return FakeStorage()


@pytest.fixture
def repo():
    return FakeImageRepository()


@pytest.fixture
def service(repo, storage):
    projects = ProjectService(FakeProjectRepository())
    projects.create_project("Shelf")
    return ImageService(repo, storage, projects)


def error_of(fn):
    with pytest.raises(ApiError) as e:
        fn()
    return e.value.status, e.value.code


# ---------- upload ----------
def test_upload_stores_original_and_thumbnail_and_creates_an_unlabeled_row(service, storage):
    result = service.upload(1, [upload("a.jpg", jpg((640, 480)))])
    assert result.skipped == []
    img = result.added[0]
    assert (img.file_name, img.width, img.height, img.status, img.box_count, img.flagged) == ("a.jpg", 640, 480, "unlabeled", 0, False)

    row = service.repo.get(img.id)
    assert row.stem == "a"
    assert row.storage_path.startswith("1/") and row.storage_path.endswith(".jpg")
    assert row.thumb_path.startswith("1/thumbs/") and row.thumb_path.endswith(".jpg")
    assert storage.objects[("images", row.storage_path)][0] == upload("a.jpg", jpg((640, 480))).content
    assert storage.objects[("images", row.thumb_path)][1] == "image/jpeg"


def test_folder_parts_are_stripped_from_file_names(service):
    assert service.upload(1, [upload("shelf/day1\\b.png")]).added[0].file_name == "b.png"


def test_files_that_are_not_images_are_skipped_with_a_reason(service):
    result = service.upload(1, [upload("notes.txt"), upload("broken.jpg", b"garbage"), upload("ok.jpg")])
    assert [a.file_name for a in result.added] == ["ok.jpg"]
    assert [(s.file_name, s.reason) for s in result.skipped] == [
        ("notes.txt", "not a supported image type (jpg, jpeg, png, bmp, webp)"),
        ("broken.jpg", "can't be opened as an image"),
    ]


def test_a_file_name_already_in_the_project_or_twice_in_one_upload_is_skipped(service):
    service.upload(1, [upload("a.jpg")])
    result = service.upload(1, [upload("a.jpg"), upload("b.jpg"), upload("b.jpg")])
    assert [a.file_name for a in result.added] == ["b.jpg"]
    assert [(s.file_name, s.reason) for s in result.skipped] == [
        ("a.jpg", "already in this project"), ("b.jpg", "already in this project")]


def test_upload_to_a_missing_project_is_404(service):
    assert error_of(lambda: service.upload(9, [upload("a.jpg")])) == (404, "PROJECT_NOT_FOUND")


def test_storage_failure_is_502(service, storage):
    storage.fail_with = StorageError(503, "storage down")
    assert error_of(lambda: service.upload(1, [upload("a.jpg")])) == (502, "STORAGE_UNAVAILABLE")


# ---------- list / filters ----------
@pytest.fixture
def mixed(service, repo):
    names = ["c.jpg", "a.jpg", "b.jpg", "d.jpg", "e.jpg"]
    ids = {i.file_name: i.id for i in service.upload(1, [upload(n) for n in names]).added}
    repo.rows[ids["a.jpg"]].status = "auto"
    repo.rows[ids["b.jpg"]].status = "reviewed"
    repo.rows[ids["b.jpg"]].flagged = True
    repo.rows[ids["c.jpg"]].status = "error"
    repo.rows[ids["d.jpg"]].status = "edited"
    return ids


def test_list_is_sorted_by_file_name_with_counts_for_every_filter(service, mixed):
    page = service.list_images(1, "all")
    assert [i.file_name for i in page.items] == ["a.jpg", "b.jpg", "c.jpg", "d.jpg", "e.jpg"]
    assert page.counts == {"all": 5, "unlabeled": 1, "auto": 1, "edited": 1, "reviewed": 1, "flagged": 1, "error": 1}


@pytest.mark.parametrize("flt,expected", [
    ("unlabeled", ["e.jpg"]), ("auto", ["a.jpg"]), ("edited", ["d.jpg"]),
    ("reviewed", ["b.jpg"]), ("flagged", ["b.jpg"]), ("error", ["c.jpg"]),
])
def test_each_filter_picks_the_right_images(service, mixed, flt, expected):
    assert [i.file_name for i in service.list_images(1, flt).items] == expected


def test_unknown_filter_is_400(service):
    assert error_of(lambda: service.list_images(1, "pink")) == (400, "UNKNOWN_FILTER")


def test_listing_a_missing_project_is_404(service):
    assert error_of(lambda: service.list_images(9, "all")) == (404, "PROJECT_NOT_FOUND")


# ---------- one image / links ----------
def test_get_image_and_missing_image(service, mixed):
    assert service.get_image(mixed["b.jpg"]).flagged is True
    assert error_of(lambda: service.get_image(999)) == (404, "IMAGE_NOT_FOUND")


def test_thumb_and_file_links_are_signed_storage_urls(service, mixed, repo):
    row = repo.get(mixed["a.jpg"])
    assert service.thumb_url(row.id) == f"http://storage.test/images/{row.thumb_path}?expires=3600"
    assert service.file_url(row.id) == f"http://storage.test/images/{row.storage_path}?expires=3600"


# ---------- status and flag ----------
def test_update_state_changes_only_what_is_given(service, mixed, repo):
    out = service.update_state(mixed["a.jpg"], status="reviewed", note="checked")
    assert (out.status, out.note, out.flagged) == ("reviewed", "checked", False)
    out = service.update_state(mixed["a.jpg"], flagged=True, flag_reason="unsure", flag_note="left can")
    assert (out.status, out.flagged, out.flag_reason, out.flag_note) == ("reviewed", True, "unsure", "left can")


def test_update_state_refuses_an_unknown_status(service, mixed):
    assert error_of(lambda: service.update_state(mixed["a.jpg"], status="done")) == (400, "UNKNOWN_STATUS")


# ---------- flag (from the review panel) ----------
def test_flag_with_reason_and_note_keeps_the_status(service, mixed):
    service.update_state(mixed["a.jpg"], status="reviewed")
    out = service.set_flag(mixed["a.jpg"], True, " wrong class ", "left\ncan")
    assert (out.status, out.flagged, out.flag_reason, out.flag_note) == ("reviewed", True, "wrong class", "left can")


def test_unflag_clears_reason_and_note(service, mixed):
    service.set_flag(mixed["a.jpg"], True, "unsure", "x")
    out = service.set_flag(mixed["a.jpg"], False, "ignored", "ignored")
    assert (out.flagged, out.flag_reason, out.flag_note) == (False, "", "")


# ---------- for the AI queue and the worker ----------
def test_ids_with_status_lists_matching_images_by_name_or_all_when_no_status_given(service, repo):
    added = service.upload(1, [upload("c.jpg"), upload("a.jpg"), upload("b.jpg")]).added
    ids = {i.file_name: i.id for i in added}
    repo.get(ids["b.jpg"]).status = "error"
    repo.get(ids["c.jpg"]).status = "reviewed"

    assert service.ids_with_status(1, ["unlabeled", "error"]) == [ids["a.jpg"], ids["b.jpg"]]
    assert service.ids_with_status(1, None) == [ids["a.jpg"], ids["b.jpg"], ids["c.jpg"]]


def test_ids_with_status_of_a_missing_project_is_404(service):
    assert error_of(lambda: service.ids_with_status(42, None)) == (404, "PROJECT_NOT_FOUND")


def test_download_original_returns_the_uploaded_bytes(service):
    data = jpg((64, 32))
    image = service.upload(1, [upload("a.jpg", data)]).added[0]
    assert service.download_original(image.id) == data


def test_download_original_when_storage_is_down_is_502(service, storage):
    image = service.upload(1, [upload("a.jpg")]).added[0]
    storage.fail_with = StorageError(0, "connection refused")
    assert error_of(lambda: service.download_original(image.id)) == (502, "STORAGE_UNAVAILABLE")
