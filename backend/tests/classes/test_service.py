"""SKU / class rules. Same behaviour as today's Project.add_class/update_class (see tests/legacy),
except that a taken or blank name is now an error the UI can show instead of being silently ignored."""
import pytest

from annotator.classes.schemas import ClassCreate, ClassUpdate
from annotator.classes.service import ClassService
from annotator.common.problem import ApiError
from annotator.project.service import ProjectService
from tests.fakes import FakeClassRepository, FakeProjectRepository


@pytest.fixture
def projects():
    return ProjectService(FakeProjectRepository())


@pytest.fixture
def service(projects):
    projects.create_project("Shelf")
    return ClassService(FakeClassRepository(), projects)


def add(service, name, prompt="", description="", project_id=1):
    return service.add_class(project_id, ClassCreate(name=name, detector_prompt=prompt, description=description))


def error_of(fn):
    with pytest.raises(ApiError) as e:
        fn()
    return e.value.status, e.value.code


# ---------- add ----------
def test_classes_get_the_next_index_in_order(service):
    assert [add(service, n).index for n in ("can", "bottle", "jar")] == [0, 1, 2]
    assert [c.name for c in service.list_classes(1)] == ["can", "bottle", "jar"]


def test_name_is_cleaned_to_one_word_with_underscores(service):
    assert add(service, "  tuna   400g\n").name == "tuna_400g"


def test_prompt_and_description_are_flattened_to_one_line(service):
    c = add(service, "sardine", "red  tin\ncan", "Short red tin.\nYellow label.")
    assert (c.detector_prompt, c.description) == ("red tin can", "Short red tin. Yellow label.")


def test_taken_name_ignoring_capitals_is_409(service):
    add(service, "can")
    assert error_of(lambda: add(service, "CAN")) == (409, "CLASS_NAME_TAKEN")


def test_blank_name_is_400(service):
    assert error_of(lambda: add(service, "   ")) == (400, "CLASS_NAME_REQUIRED")


def test_adding_to_a_missing_project_is_404(service):
    assert error_of(lambda: add(service, "can", project_id=42)) == (404, "PROJECT_NOT_FOUND")


# ---------- update ----------
def test_rename_keeps_the_index(service):
    add(service, "can")
    add(service, "bottle")
    renamed = service.update_class(1, 0, ClassUpdate(name="tin can"))
    assert (renamed.index, renamed.name) == (0, "tin_can")
    assert [c.name for c in service.list_classes(1)] == ["tin_can", "bottle"]


def test_changing_only_the_case_of_its_own_name_is_allowed(service):
    add(service, "can")
    assert service.update_class(1, 0, ClassUpdate(name="Can")).name == "Can"


def test_rename_to_a_taken_name_is_409(service):
    add(service, "can")
    add(service, "bottle")
    assert error_of(lambda: service.update_class(1, 1, ClassUpdate(name="can"))) == (409, "CLASS_NAME_TAKEN")


def test_rename_to_blank_is_400(service):
    add(service, "can")
    assert error_of(lambda: service.update_class(1, 0, ClassUpdate(name="  "))) == (400, "CLASS_NAME_REQUIRED")


def test_fields_left_out_are_unchanged(service):
    add(service, "can", "metal can", "Silver")
    updated = service.update_class(1, 0, ClassUpdate(description="Silver, red lid"))
    assert (updated.name, updated.detector_prompt, updated.description) == ("can", "metal can", "Silver, red lid")


def test_prompt_can_be_cleared(service):
    add(service, "can", "metal can")
    assert service.update_class(1, 0, ClassUpdate(detector_prompt="")).detector_prompt == ""


def test_unknown_index_is_404(service):
    assert error_of(lambda: service.update_class(1, 7, ClassUpdate(name="x"))) == (404, "CLASS_NOT_FOUND")


def test_listing_classes_of_a_missing_project_is_404(service):
    assert error_of(lambda: service.list_classes(42)) == (404, "PROJECT_NOT_FOUND")


# ---------- get one ----------
def test_get_class_returns_one_class(service):
    add(service, "can")
    add(service, "jar", prompt="glass jar")
    assert service.get_class(1, 1).model_dump() == {"index": 1, "name": "jar", "detector_prompt": "glass jar",
                                                    "description": ""}


def test_get_unknown_class_is_404(service):
    assert error_of(lambda: service.get_class(1, 5)) == (404, "CLASS_NOT_FOUND")


# ---------- import helpers ----------
def test_import_classes_adds_the_whole_list_in_order_when_the_project_has_none(service):
    created = service.import_classes(1, [("sardine", "red tin", "Short red tin"), ("spray bottle", "", "")])
    assert created == ["sardine", "spray_bottle"]
    assert [(c.index, c.name, c.detector_prompt) for c in service.list_classes(1)] == [
        (0, "sardine", "red tin"), (1, "spray_bottle", "")]


def test_import_classes_keeps_existing_classes(service):
    add(service, "can")
    assert service.import_classes(1, [("other", "", "")]) == []
    assert [c.name for c in service.list_classes(1)] == ["can"]


def test_import_classes_never_shifts_an_index_on_a_repeated_or_blank_name(service):
    created = service.import_classes(1, [("can", "", ""), ("CAN", "", ""), ("", "", ""), ("jar", "", "")])
    assert created == ["can", "CAN_1", "class_2", "jar"]
    assert [c.index for c in service.list_classes(1)] == [0, 1, 2, 3]


def test_ensure_indexes_adds_placeholder_classes_up_to_the_highest_index(service):
    add(service, "can")
    assert service.ensure_indexes(1, 3) == ["class_1", "class_2", "class_3"]
    assert service.ensure_indexes(1, 2) == []
    assert [c.name for c in service.list_classes(1)] == ["can", "class_1", "class_2", "class_3"]


def test_ensure_indexes_picks_a_free_placeholder_name(service):
    add(service, "class_1")
    assert service.ensure_indexes(1, 1) == ["class_1_1"]
