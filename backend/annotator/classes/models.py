from sqlalchemy import BigInteger, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from annotator.db.base import Base


class ProjectClass(Base):
    """One SKU / YOLO class. `class_index` is the YOLO class ID and never changes.
    Table created by V1__projects_classes.sql."""

    __tablename__ = "classes"

    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    class_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    detector_prompt: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
