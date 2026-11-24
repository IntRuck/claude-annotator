from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from annotator.label.models import Box


class LabelRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_for_image(self, image_id: int) -> list[Box]:
        return list(self.session.scalars(select(Box).where(Box.image_id == image_id).order_by(Box.id)))

    def replace(self, project_id: int, image_id: int, boxes: list[dict], source: str) -> list[Box]:
        """Swap the image's whole box set. Boxes are dicts with cls, x1, y1, x2, y2 and optional conf and source
        (`source` is used for boxes that don't say)."""
        self.session.execute(delete(Box).where(Box.image_id == image_id))
        rows = [Box(image_id=image_id, project_id=project_id, class_index=b["cls"], x1=b["x1"], y1=b["y1"],
                    x2=b["x2"], y2=b["y2"], conf=b.get("conf"), source=b.get("source") or source) for b in boxes]
        self.session.add_all(rows)
        self.session.flush()
        return rows
