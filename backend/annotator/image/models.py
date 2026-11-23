from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Identity, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from annotator.db.base import Base

STATUSES = ("unlabeled", "auto", "edited", "reviewed", "error")


class Image(Base):
    """One photo in a project. Table created by V2__images.sql.

    `flagged` ("check this later") is separate from `status`, so an approved image can still be flagged.
    """

    __tablename__ = "images"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("projects.id", ondelete="CASCADE"))
    file_name: Mapped[str] = mapped_column(Text)
    stem: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(Text)
    thumb_path: Mapped[str] = mapped_column(Text)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default="unlabeled")
    note: Mapped[str] = mapped_column(Text, server_default="")
    flagged: Mapped[bool] = mapped_column(Boolean, server_default="false")
    flag_reason: Mapped[str] = mapped_column(Text, server_default="")
    flag_note: Mapped[str] = mapped_column(Text, server_default="")
    box_count: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
