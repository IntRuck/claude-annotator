from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from annotator.db.base import Base


class WorkerStatus(Base):
    """One running worker's heartbeat. Table created by V7__worker_status.sql."""

    __tablename__ = "worker_status"

    worker_id: Mapped[str] = mapped_column(Text, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    engines: Mapped[dict] = mapped_column(JSONB, server_default="{}")


class EnginePause(Base):
    """An engine that hit a usage limit; its jobs wait until Resume."""

    __tablename__ = "engine_pauses"

    engine: Mapped[str] = mapped_column(Text, primary_key=True)
    reason: Mapped[str] = mapped_column(Text)
    paused_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
