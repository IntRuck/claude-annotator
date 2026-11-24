"""RealtimeService: a NOTIFY payload from the database trigger -> the message the browser gets."""
import json

import pytest

from annotator.classes.schemas import ClassCreate
from annotator.classes.service import ClassService
from annotator.image.service import ImageService
from annotator.project.service import ProjectService
from annotator.realtime.service import RealtimeService
from tests.fakes import FakeClassRepository, FakeImageRepository, FakeProjectRepository, FakeStorage


@pytest.fixture
def service():
    projects = ProjectService(FakeProjectRepository())
    projects.create_project("Shelf")
    images_repo = FakeImageRepository()
    images_repo.add(1, file_name="a.jpg", stem="a", storage_path="p", thumb_path="t", width=100, height=50)
    classes = ClassService(FakeClassRepository(), projects)
    classes.add_class(1, ClassCreate(name="can", description="red tin"))
    return RealtimeService(ImageService(images_repo, FakeStorage(), projects), classes)


def payload(**fields) -> str:
    return json.dumps(fields)


def test_changed_image_becomes_its_full_dto_for_its_project(service):
    project_id, message = service.to_message(payload(type="images", op="update", id=1, projectId=1))
    assert project_id == 1
    assert message["type"] == "images"
    assert message["op"] == "update"
    assert message["data"] == {
        "id": 1, "projectId": 1, "fileName": "a.jpg", "width": 100, "height": 50, "status": "unlabeled", "note": "",
        "flagged": False, "flagReason": "", "flagNote": "", "boxCount": 0, "updatedAt": "2026-11-23T00:00:00Z",
    }


def test_new_image_is_sent_as_insert(service):
    _, message = service.to_message(payload(type="images", op="insert", id=1, projectId=1))
    assert (message["op"], message["data"]["fileName"]) == ("insert", "a.jpg")


def test_deleted_image_sends_only_its_id(service):
    assert service.to_message(payload(type="images", op="delete", id=9, projectId=1)) == (
        1, {"type": "images", "op": "delete", "data": {"id": 9}})


def test_image_gone_by_the_time_we_read_it_is_sent_as_a_delete(service):
    assert service.to_message(payload(type="images", op="update", id=9, projectId=1)) == (
        1, {"type": "images", "op": "delete", "data": {"id": 9}})


def test_changed_class_becomes_its_dto(service):
    assert service.to_message(payload(type="classes", op="update", id=0, projectId=1)) == (
        1, {"type": "classes", "op": "update",
            "data": {"index": 0, "name": "can", "detectorPrompt": "", "description": "red tin"}})


def test_class_gone_by_the_time_we_read_it_is_sent_as_a_delete(service):
    assert service.to_message(payload(type="classes", op="update", id=4, projectId=1)) == (
        1, {"type": "classes", "op": "delete", "data": {"index": 4}})


@pytest.mark.parametrize("raw", [
    "not json",
    json.dumps({"type": "robots", "op": "update", "id": 1, "projectId": 1}),
    json.dumps({"type": "images", "op": "update"}),
    json.dumps({"type": "images", "op": "truncate", "id": 1, "projectId": 1}),
])
def test_payloads_it_does_not_understand_are_skipped(service, raw):
    assert service.to_message(raw) is None
