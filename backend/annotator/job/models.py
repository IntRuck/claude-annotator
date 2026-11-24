from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from annotator.db.base import Base

KINDS = ("annotate", "refine")
OPEN = ("queued", "running")
FINISHED = ("done", "failed", "cancelled")


class Job(Base):
    """One image for one engine. Table created by V6__jobs_activity.sql."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("projects.id", ondelete="CASCADE"))
    image_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("images.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    engine: Mapped[str] = mapped_column(Text)
    options: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    status: Mapped[str] = mapped_column(Text, server_default="queued")
    error: Mapped[str] = mapped_column(Text, server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
