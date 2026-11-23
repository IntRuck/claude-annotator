import pytest
from sqlalchemy.exc import IntegrityError

from annotator.classes.repository import ClassRepository
from annotator.image.models import Image
from annotator.image.repository import ImageRepository
from annotator.label.repository import LabelRepository
from annotator.project.repository import ProjectRepository

pytestmark = pytest.mark.db


@pytest.fixture
def ids(db_session):
    pid = ProjectRepository(db_session).create("P").id
    classes = ClassRepository(db_session)
    classes.add(pid, "can", "", "")
    classes.add(pid, "bottle", "", "")
    image = ImageRepository(db_session).add(pid, file_name="a.jpg", stem="a", storage_path="p", thumb_path="t",
                                            width=100, height=50)
    return pid, image.id


def box(cls, x1=0.1, y1=0.1, x2=0.5, y2=0.5, **kw):
    return {"cls": cls, "x1": x1, "y1": y1, "x2": x2, "y2": y2, **kw}


def box_count(db_session, image_id):
    db_session.expire_all()
    return db_session.get(Image, image_id).box_count


def test_replace_stores_boxes_in_order_and_swaps_the_whole_set(db_session, ids):
    pid, image_id = ids
    repo = LabelRepository(db_session)
    repo.replace(pid, image_id, [box(0), box(1, conf=0.8)], source="import")
    assert [(b.class_index, b.source, b.conf) for b in repo.list_for_image(image_id)] == [(0, "import", None), (1, "import", pytest.approx(0.8))]

    repo.replace(pid, image_id, [box(1, 0.2, 0.2, 0.3, 0.3)], source="human")
    rows = repo.list_for_image(image_id)
    assert [(b.class_index, b.x1, b.source) for b in rows] == [(1, pytest.approx(0.2), "human")]


def test_database_keeps_box_count_in_step(db_session, ids):
    pid, image_id = ids
    repo = LabelRepository(db_session)
    repo.replace(pid, image_id, [box(0), box(0), box(1)], source="import")
    assert box_count(db_session, image_id) == 3
    repo.replace(pid, image_id, [box(1)], source="human")
    assert box_count(db_session, image_id) == 1
    repo.replace(pid, image_id, [], source="human")
    assert box_count(db_session, image_id) == 0


def test_box_must_use_a_class_of_the_project(db_session, ids):
    pid, image_id = ids
    with pytest.raises(IntegrityError):
        LabelRepository(db_session).replace(pid, image_id, [box(7)], source="import")


def test_corners_must_be_inside_the_image_and_in_order(db_session, ids):
    pid, image_id = ids
    with pytest.raises(IntegrityError):
        LabelRepository(db_session).replace(pid, image_id, [box(0, x1=0.6, x2=0.2)], source="import")


def test_deleting_an_image_deletes_its_boxes(db_session, ids):
    pid, image_id = ids
    repo = LabelRepository(db_session)
    repo.replace(pid, image_id, [box(0)], source="import")
    db_session.delete(db_session.get(Image, image_id))
    db_session.flush()
    assert repo.list_for_image(image_id) == []
