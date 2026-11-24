import pytest

from annotator.activity.service import ActivityService
from annotator.common.problem import ApiError
from annotator.project.service import ProjectService
from tests.fakes import FakeActivityRepository, FakeProjectRepository


@pytest.fixture
def service():
    projects = ProjectService(FakeProjectRepository())
    projects.create_project("Shelf")
    return ActivityService(FakeActivityRepository(), projects)


def error_of(fn):
    with pytest.raises(ApiError) as e:
        fn()
    return e.value.status, e.value.code


def test_log_returns_the_entry_dto(service):
    entry = service.log(1, "a.jpg: 3 box(es)", job_id=4, image_id=2)
    assert entry.model_dump(by_alias=True, mode="json") == {
        "id": 1, "level": "info", "message": "a.jpg: 3 box(es)", "jobId": 4, "imageId": 2,
        "createdAt": "2026-11-23T00:00:00Z"}


def test_messages_are_one_line_and_not_endless(service):
    entry = service.log(1, "boom\n" + "x" * 3000, level="error")
    assert "\n" not in entry.message
    assert len(entry.message) <= 1000


def test_recent_is_newest_first(service):
    for n in range(3):
        service.log(1, f"line {n}")
    assert [e.message for e in service.list_recent(1, limit=2)] == ["line 2", "line 1"]


def test_limit_must_be_between_1_and_500(service):
    assert error_of(lambda: service.list_recent(1, limit=0)) == (400, "BAD_LIMIT")
    assert error_of(lambda: service.list_recent(1, limit=501)) == (400, "BAD_LIMIT")


def test_activity_of_a_missing_project_is_404(service):
    assert error_of(lambda: service.list_recent(42, limit=10)) == (404, "PROJECT_NOT_FOUND")


def test_get_entry_finds_one_or_404(service):
    service.log(1, "hello")
    assert service.get_entry(1).message == "hello"
    assert error_of(lambda: service.get_entry(9)) == (404, "ACTIVITY_NOT_FOUND")
