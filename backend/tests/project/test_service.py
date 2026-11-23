import pytest

from annotator.common.problem import ApiError
from annotator.project.service import ProjectService
from tests.fakes import FakeProjectRepository


@pytest.fixture
def service():
    return ProjectService(FakeProjectRepository())


def test_create_project_trims_the_name(service):
    project = service.create_project("  Shelf scans  ")
    assert project.name == "Shelf scans"
    assert project.id == 1


def test_create_project_needs_a_name(service):
    with pytest.raises(ApiError) as e:
        service.create_project("   ")
    assert (e.value.status, e.value.code) == (400, "PROJECT_NAME_REQUIRED")


def test_list_projects_newest_first(service):
    service.create_project("First")
    service.create_project("Second")
    assert [p.name for p in service.list_projects()] == ["Second", "First"]


def test_get_missing_project_is_404(service):
    with pytest.raises(ApiError) as e:
        service.get_project(99)
    assert (e.value.status, e.value.code) == (404, "PROJECT_NOT_FOUND")


def test_get_project_returns_its_fields(service):
    created = service.create_project("Shelf")
    got = service.get_project(created.id)
    assert (got.id, got.name, got.created_at) == (created.id, "Shelf", created.created_at)
