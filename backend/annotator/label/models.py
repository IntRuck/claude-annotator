from sqlalchemy import REAL, BigInteger, Double, ForeignKey, Identity, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from annotator.db.base import Base

SOURCES = ("ai", "human", "import")


class Box(Base):
    """One box on one image, corners as fractions of the image (0-1). Table created by V3__boxes.sql.
    images.box_count is kept in step by a database trigger. `points` (V9) is the object's outline, [[x, y], ...]
    in 0-1, or None for a plain box; when set, the corners are the smallest box around it."""

    __tablename__ = "boxes"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    image_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("images.id", ondelete="CASCADE"))
    project_id: Mapped[int] = mapped_column(BigInteger)
    class_index: Mapped[int] = mapped_column(Integer)
    x1: Mapped[float] = mapped_column(Double)
    y1: Mapped[float] = mapped_column(Double)
    x2: Mapped[float] = mapped_column(Double)
    y2: Mapped[float] = mapped_column(Double)
    conf: Mapped[float | None] = mapped_column(REAL, nullable=True)
    source: Mapped[str] = mapped_column(Text)
    # none_as_null: None must be SQL NULL (a plain box), not the JSON value null, which the V9 check refuses.
    points: Mapped[list | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
