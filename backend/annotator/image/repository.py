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

    def summary_by_project(self) -> dict[int, dict]:
        """Per project that has images: counts by status, flagged, the newest change, and the first image added
        (the cover on the projects page). One query for all projects."""
        columns = [Image.project_id, func.count().label("all"),
                   func.count().filter(Image.flagged.is_(True)).label("flagged")]
        columns += [func.count().filter(Image.status == s).label(s) for s in STATUSES]
        columns += [func.max(Image.updated_at).label("last_changed_at"), func.min(Image.id).label("cover_image_id")]
        rows = self.session.execute(select(*columns).group_by(Image.project_id))
        return {r.project_id: {k: v for k, v in r._asdict().items() if k != "project_id"} for r in rows}

    def file_paths(self, project_id: int) -> list[str]:
        """Every original and thumbnail path of the project, for removing its files from storage."""
        rows = self.session.execute(select(Image.storage_path, Image.thumb_path).where(Image.project_id == project_id))
        return [path for row in rows for path in row]

    def ids_with_status(self, project_id: int, statuses: list[str] | None) -> list[int]:
        """Image ids by file name; all of the project's images when `statuses` is None."""
        stmt = select(Image.id).where(Image.project_id == project_id)
        if statuses is not None:
            stmt = stmt.where(Image.status.in_(statuses))
        return list(self.session.scalars(stmt.order_by(Image.file_name)))

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
