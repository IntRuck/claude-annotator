from sqlalchemy import func, select
from sqlalchemy.orm import Session

from annotator.image.models import STATUSES, Image


class ImageRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, image_id: int) -> Image | None:
        return self.session.get(Image, image_id)

    def list_for_project(self, project_id: int, image_filter: str) -> list[Image]:
        stmt = select(Image).where(Image.project_id == project_id)
        if image_filter == "flagged":
            stmt = stmt.where(Image.flagged.is_(True))
        elif image_filter != "all":
            stmt = stmt.where(Image.status == image_filter)
        return list(self.session.scalars(stmt.order_by(Image.file_name)))

    def counts(self, project_id: int) -> dict[str, int]:
        columns = [func.count().label("all"), func.count().filter(Image.flagged.is_(True)).label("flagged")]
        columns += [func.count().filter(Image.status == s).label(s) for s in STATUSES]
        row = self.session.execute(select(*columns).where(Image.project_id == project_id)).one()
        counts = row._asdict()
        return {k: counts[k] for k in ("all", "unlabeled", "auto", "edited", "reviewed", "flagged", "error")}

    def find_by_names(self, project_id: int, names: list[str]) -> list[Image]:
        if not names:
            return []
        stmt = select(Image).where(Image.project_id == project_id, Image.file_name.in_(names))
        return list(self.session.scalars(stmt.order_by(Image.file_name)))

    def save(self, row: Image) -> Image:
        """Write changes to an image row and bump updated_at, the version the editor's save-conflict check uses.
        clock_timestamp(), not now(): now() is fixed for a whole transaction, so two saves in one transaction
        would get the same version."""
        row.updated_at = func.clock_timestamp()
        self.session.flush()
        self.session.refresh(row)
        return row

    def add(self, project_id: int, *, file_name: str, stem: str, storage_path: str, thumb_path: str,
            width: int, height: int) -> Image:
        row = Image(project_id=project_id, file_name=file_name, stem=stem, storage_path=storage_path,
                    thumb_path=thumb_path, width=width, height=height)
        self.session.add(row)
        self.session.flush()
        self.session.refresh(row)
        return row
