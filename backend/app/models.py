"""SQLAlchemy 2.0 models (Mapped / mapped_column style)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Novel(Base):
    __tablename__ = "novels"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(512), index=True)
    author: Mapped[str] = mapped_column(String(256), default="")
    source_url: Mapped[str] = mapped_column(String(1024), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    cover_path: Mapped[str] = mapped_column(String(1024), default="")
    file_type: Mapped[str] = mapped_column(String(16), default="txt")  # txt / epub
    category: Mapped[str] = mapped_column(String(64), default="未分类")
    total_chapters: Mapped[int] = mapped_column(Integer, default=0)
    read_chapters: Mapped[int] = mapped_column(Integer, default=0)
    last_chapter_idx: Mapped[int] = mapped_column(Integer, default=0)
    last_scroll_pos: Mapped[float] = mapped_column(Float, default=0.0)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="novel", cascade="all, delete-orphan", order_by="Chapter.idx"
    )
    notes: Mapped[list["Note"]] = relationship(
        back_populates="novel", cascade="all, delete-orphan"
    )


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (Index("ix_chapters_novel_idx", "novel_id", "idx"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    novel_id: Mapped[str] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)  # 0-based order
    title: Mapped[str] = mapped_column(String(512), default="")
    content_path: Mapped[str] = mapped_column(String(1024), default="")  # relative to data dir
    content: Mapped[str] = mapped_column(Text, default="")  # inline content (small novels)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    novel: Mapped["Novel"] = relationship(back_populates="chapters")


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    novel_id: Mapped[str] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), index=True)
    chapter_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    chapter_title: Mapped[str] = mapped_column(String(512), default="")
    chapter_idx: Mapped[int] = mapped_column(Integer, default=0)
    excerpt: Mapped[str] = mapped_column(Text, default="")   # selected text
    content: Mapped[str] = mapped_column(Text, default="")   # user note
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    novel: Mapped["Novel"] = relationship(back_populates="notes")


class MediaItem(Base):
    __tablename__ = "media"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    media_type: Mapped[str] = mapped_column(String(16), index=True)  # image/video/audio/page/doc
    title: Mapped[str] = mapped_column(String(512), default="")
    source_url: Mapped[str] = mapped_column(String(1024), default="")
    file_path: Mapped[str] = mapped_column(String(1024), default="")  # relative to data dir
    thumbnail_path: Mapped[str] = mapped_column(String(1024), default="")
    mime_type: Mapped[str] = mapped_column(String(128), default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    duration: Mapped[float] = mapped_column(Float, default=0.0)      # seconds, av only
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DownloadTask(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tool: Mapped[str] = mapped_column(String(64), index=True)
    task_type: Mapped[str] = mapped_column(String(32), default="download")  # download/search
    url: Mapped[str] = mapped_column(String(2048), default="")
    title: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    # queued / running / paused / completed / failed / canceled
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100
    speed: Mapped[str] = mapped_column(String(64), default="")
    eta: Mapped[str] = mapped_column(String(64), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    output_dir: Mapped[str] = mapped_column(String(1024), default="")
    argv: Mapped[list] = mapped_column(JSON, default=list)       # command to (re)execute
    dest_type: Mapped[str] = mapped_column(String(16), default="media")  # media / novel
    log_tail: Mapped[list] = mapped_column(JSON, default=list)   # last N log lines
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReadingSession(Base):
    __tablename__ = "reading_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    novel_id: Mapped[str] = mapped_column(String(32), ForeignKey("novels.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    chapters_read: Mapped[int] = mapped_column(Integer, default=0)
    day: Mapped[str] = mapped_column(String(10), index=True, default="")  # YYYY-MM-DD


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON, default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class AiSummary(Base):
    __tablename__ = "ai_summaries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    novel_id: Mapped[str] = mapped_column(String(32), index=True)
    chapter_id: Mapped[str] = mapped_column(String(32), index=True)
    chapter_idx: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
