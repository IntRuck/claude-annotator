from annotator.classes.service import ClassService
from annotator.common.problem import ApiError
from annotator.health.report import build_report
from annotator.health.schemas import HealthReport
from annotator.image.service import ImageService
from annotator.label.service import LabelService

MAX_LOW_COUNT = 100_000


class HealthService:
    """The dataset health check, computed from the database on request (like today's Health check button)."""

    def __init__(self, images: ImageService, classes: ClassService, labels: LabelService):
        self.images = images
        self.classes = classes
        self.labels = labels

    def report(self, project_id: int, low_count: int = 100) -> HealthReport:
        """`low_count`: classes with fewer boxes than this get a "low" warning."""
        if not 1 <= low_count <= MAX_LOW_COUNT:
            raise ApiError(400, "BAD_LOW_COUNT", f"'Warn below' must be between 1 and {MAX_LOW_COUNT} boxes.")
        classes = self.classes.list_classes(project_id)  # also checks the project exists
        images = self.images.list_images(project_id, "all").items
        boxes = self.labels.boxes_by_image(project_id)
        report = build_report([(c.index, c.name) for c in classes], images, boxes, low_count)
        return HealthReport.model_validate(report)
