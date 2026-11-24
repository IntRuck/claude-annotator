"""LabelingService: one claimed job -> boxes on the image, status, note and a log line (today's Worker._run)."""
import io

from PIL import Image

from annotator.labeling.service import run_engine
from tests.labeling.conftest import FakeEngine

CAN = {"cls": 0, "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5}
JAR = {"cls": 1, "x1": 0.6, "y1": 0.2, "x2": 0.9, "y2": 0.8}


def claimed(w, name="a.jpg"):
    image_id = w.upload(name)
    w.queue()
    return image_id, w.jobs.claim_next()


def test_load_reads_the_original_and_the_class_list(w):
    image_id, job = claimed(w)
    task = w.labeling.load(job)

    assert task.image == w.images.download_original(image_id)
    assert task.file_name == "a.jpg"
    assert task.classes == ["tuna_can", "jar"]
    assert task.prompts == ["tuna can", "glass jar"]      # detector prompt, else the name with spaces
    assert task.descs == ["red tin", ""]
    assert task.indexes == [0, 1]


def test_an_image_labelled_by_hand_before_its_turn_is_skipped(w):
    image_id, job = claimed(w)
    w.image_repo.get(image_id).status = "edited"

    assert w.labeling.load(job) is None

    assert w.job_repo.get(job.id).status == "cancelled"
    assert w.activity_repo.messages()[-1] == "a.jpg: skipped, it was edited by hand before its turn came"


def test_one_image_asked_for_on_purpose_is_never_skipped(w):
    image_id = w.upload("a.jpg")
    w.image_repo.get(image_id).status = "reviewed"
    w.queue(target="image", image_id=image_id)
    assert w.labeling.load(w.jobs.claim_next()) is not None


def test_run_engine_shrinks_the_photo_passes_the_classes_and_maps_positions_to_class_indexes(w):
    image_id = w.upload("big.jpg", size=(3000, 1000))
    w.queue()
    task = w.labeling.load(w.jobs.claim_next())
    task.indexes = [4, 7]             # positions in the list the engine saw -> real class indexes
    engine = FakeEngine([([CAN, JAR, {**CAN, "cls": 5}], {"pear"})])

    outcome = run_engine(task, lambda name, options: engine)

    sent = Image.open(io.BytesIO(engine.calls[0]["image"]))
    assert max(sent.size) == 1568
    assert engine.calls[0]["classes"] == ["tuna_can", "jar"]
    assert engine.calls[0]["extra"] == "top shelf"
    assert [b["cls"] for b in outcome.boxes] == [4, 7]
    assert outcome.unknown == {"pear"}
    assert outcome.engine == "gemini"
    assert image_id


def test_detectors_get_the_original_photo(w):
    w.upload("a.jpg")
    w.queue()
    task = w.labeling.load(w.jobs.claim_next())
    engine = FakeEngine([([], set())], resize_input=False)
    run_engine(task, lambda name, options: engine)
    assert engine.calls[0]["image"] == task.image


def test_save_writes_ai_boxes_sets_auto_with_a_note_and_finishes_the_job(w):
    image_id, job = claimed(w)
    task = w.labeling.load(job)
    w.engine = FakeEngine([([CAN, {"cls": 1, "x1": 0.5, "y1": 0.5, "x2": 0.5005, "y2": 0.9}], {"pear", "apple"})])
    outcome = run_engine(task, w.make_engine)

    w.labeling.save(task, outcome)

    assert [b["source"] for b in w.label_repo.list_for_image(image_id)] == ["ai"]   # the tiny box is dropped
    image = w.image_repo.get(image_id)
    assert (image.status, image.note) == ("auto", "via gemini; unknown classes ignored: apple, pear")
    assert w.job_repo.get(job.id).status == "done"
    entry = w.activity_repo.rows[-1]
    assert entry.message.startswith("a.jpg: 1 box(es) in ")
    assert entry.message.endswith("s (via gemini; unknown classes ignored: apple, pear)")
    assert (entry.job_id, entry.image_id) == (job.id, image_id)


def test_fail_marks_the_image_as_an_error_with_the_reason(w):
    image_id, job = claimed(w)

    w.labeling.fail(job, RuntimeError("Gemini HTTP 500: overloaded"))

    image = w.image_repo.get(image_id)
    assert (image.status, image.note) == ("error", "gemini: Gemini HTTP 500: overloaded")
    assert (w.job_repo.get(job.id).status, w.job_repo.get(job.id).error) == ("failed", "Gemini HTTP 500: overloaded")
    entry = w.activity_repo.rows[-1]
    assert (entry.level, entry.message) == ("error", "a.jpg: ERROR Gemini HTTP 500: overloaded")


def test_a_usage_limit_pauses_the_engine_and_keeps_every_image_waiting(w):
    image_id = w.upload("a.jpg")
    w.upload("b.jpg")
    w.queue()
    job = w.jobs.claim_next()

    w.labeling.limit_reached(job, "Gemini daily free quota used up")

    assert w.status(image_id) == "unlabeled"
    assert [j.status for j in w.job_repo.rows.values()] == ["queued", "queued"]
    assert [(p.engine, p.reason) for p in w.worker_repo.pauses()] == [("gemini", "Gemini daily free quota used up")]
    entry = w.activity_repo.rows[-1]
    assert (entry.level, entry.message) == ("warning", "Gemini usage limit: Gemini daily free quota used up. "
                                                       "Paused; 2 image(s) wait in the queue. "
                                                       "Press Resume once the limit resets.")


# ---------- refine ----------
def queued_refine(w, boxes):
    image_id = w.upload("a.jpg", size=(400, 300))
    w.give_boxes(image_id, boxes)
    w.queue(target="image", image_id=image_id, kind="refine")
    return image_id, w.jobs.claim_next()


def test_load_for_refine_brings_the_current_boxes_as_positions_in_the_class_list(w):
    _, job = queued_refine(w, [JAR, CAN])
    task = w.labeling.load(job)
    assert sorted((b["cls"], b["x1"]) for b in task.current) == [(0, 0.1), (1, 0.6)]


def test_an_annotate_job_does_not_load_the_current_boxes(w):
    _, job = claimed(w)
    assert w.labeling.load(job).current == []


def test_run_engine_for_refine_sends_a_clean_and_a_numbered_copy_and_the_boxes_on_0_1000(w):
    _, job = queued_refine(w, [CAN])
    task = w.labeling.load(job)
    engine = FakeEngine([([JAR], set())])

    outcome = run_engine(task, lambda name, options: engine)

    call = engine.calls[0]
    assert call["clean"] != call["overlay"]
    assert Image.open(io.BytesIO(call["overlay"])).size == Image.open(io.BytesIO(call["clean"])).size == (400, 300)
    assert call["current"] == [{"class": "tuna_can", "box": [100, 100, 500, 500]}]
    assert [b["cls"] for b in outcome.boxes] == [1]


def test_saving_a_refine_replaces_the_boxes(w):
    image_id, job = queued_refine(w, [CAN])
    task = w.labeling.load(job)
    w.labeling.save(task, run_engine(task, lambda name, options: FakeEngine([([JAR, CAN], set())])))
    assert sorted(b["cls"] for b in w.label_repo.list_for_image(image_id)) == [0, 1]
    assert w.status(image_id) == "auto"
