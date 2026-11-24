from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from annotator.db.base import Base

LEVELS = ("info", "warning", "error")


class ActivityEntry(Base):
    """One line of a project's activity log. Table created by V6__jobs_activity.sql."""

    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("projects.id", ondelete="CASCADE"))
    job_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("jobs.id", ondelete="SET NULL"))
    image_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("images.id", ondelete="SET NULL"))
    level: Mapped[str] = mapped_column(Text, server_default="info")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
