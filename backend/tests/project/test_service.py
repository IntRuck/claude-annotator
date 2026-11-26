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


def test_create_project_keeps_a_one_line_description(service):
    project = service.create_project("Shelf", "  Store 3 shelves,\n November  ")
    assert project.description == "Store 3 shelves, November"


def test_create_project_description_defaults_to_empty(service):
    assert service.create_project("Shelf").description == ""


def test_create_project_refuses_a_long_description(service):
    with pytest.raises(ApiError) as e:
        service.create_project("Shelf", "x" * 201)
    assert (e.value.status, e.value.code) == (400, "PROJECT_DESCRIPTION_TOO_LONG")


def test_update_project_renames_and_keeps_the_description(service):
    created = service.create_project("Shelf", "Store 3")
    updated = service.update_project(created.id, name="  Shelf A ")
    assert (updated.name, updated.description) == ("Shelf A", "Store 3")


def test_update_project_changes_only_the_description(service):
    created = service.create_project("Shelf")
    updated = service.update_project(created.id, description=" Fridge drinks ")
    assert (updated.name, updated.description) == ("Shelf", "Fridge drinks")
    assert service.get_project(created.id).description == "Fridge drinks"


def test_update_project_can_clear_the_description(service):
    created = service.create_project("Shelf", "Store 3")
    assert service.update_project(created.id, description="").description == ""


def test_update_project_needs_a_name(service):
    created = service.create_project("Shelf")
    with pytest.raises(ApiError) as e:
        service.update_project(created.id, name="  ")
    assert (e.value.status, e.value.code) == (400, "PROJECT_NAME_REQUIRED")


def test_update_project_refuses_a_long_description(service):
    created = service.create_project("Shelf")
    with pytest.raises(ApiError) as e:
        service.update_project(created.id, description="x" * 201)
    assert (e.value.status, e.value.code) == (400, "PROJECT_DESCRIPTION_TOO_LONG")


def test_update_missing_project_is_404(service):
    with pytest.raises(ApiError) as e:
        service.update_project(99, name="Shelf")
    assert (e.value.status, e.value.code) == (404, "PROJECT_NOT_FOUND")


def test_delete_project_removes_it(service):
    created = service.create_project("Shelf")
    service.delete_project(created.id)
    assert service.list_projects() == []


def test_delete_missing_project_is_404(service):
    with pytest.raises(ApiError) as e:
        service.delete_project(99)
    assert (e.value.status, e.value.code) == (404, "PROJECT_NOT_FOUND")
