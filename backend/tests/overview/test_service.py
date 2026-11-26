import logging
from datetime import timedelta

import pytest

from annotator.common.problem import ApiError
from annotator.storage.storage_service import StorageError
from tests.fakes import NOW


def by_name(world):
    return {s.name: s for s in world.service.summaries()}


def test_summary_counts_a_projects_images_and_skus(world):
    shelf = by_name(world)["Shelf"]
    assert (shelf.image_count, shelf.unlabeled, shelf.labelled, shelf.reviewed, shelf.to_approve) == (4, 1, 2, 1, 1)
    assert (shelf.flagged, shelf.errors, shelf.class_count) == (1, 1, 2)
    assert (shelf.description, shelf.cover_image_id) == ("Store 3", 1)


def test_last_changed_is_the_newest_image_change(world):
    assert by_name(world)["Shelf"].last_changed_at == NOW + timedelta(hours=2)


def test_last_changed_is_the_project_edit_when_that_is_newer(world):
    world.projects.get(1).updated_at = NOW + timedelta(days=1)
    assert by_name(world)["Shelf"].last_changed_at == NOW + timedelta(days=1)


def test_project_without_images_or_skus_has_zeros_and_no_cover(world):
    empty = by_name(world)["Empty"]
    assert (empty.image_count, empty.labelled, empty.class_count, empty.cover_image_id) == (0, 0, 0, None)
    assert empty.last_changed_at == empty.updated_at


def test_summaries_are_most_recently_changed_first(world):
    assert [s.name for s in world.service.summaries()] == ["Shelf", "Empty"]
    world.projects.get(2).updated_at = NOW + timedelta(days=1)
    assert [s.name for s in world.service.summaries()] == ["Empty", "Shelf"]


def test_delete_removes_the_project_and_its_photo_files(world):
    world.service.delete_project(1)
    assert world.projects.get(1) is None
    assert world.storage.objects == {}


def test_delete_still_succeeds_when_storage_is_down_and_logs_a_warning(world, caplog):
    world.storage.fail_with = StorageError(0, "connection refused")
    with caplog.at_level(logging.WARNING):
        world.service.delete_project(1)
    assert world.projects.get(1) is None
    assert "files" in caplog.text


def test_delete_missing_project_is_404_and_touches_no_files(world):
    with pytest.raises(ApiError) as e:
        world.service.delete_project(99)
    assert (e.value.status, e.value.code) == (404, "PROJECT_NOT_FOUND")
    assert len(world.storage.objects) == 8
