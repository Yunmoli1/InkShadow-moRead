"""Async SQLAlchemy engine & session (SQLite via aiosqlite)."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from . import config


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    f"sqlite+aiosqlite:///{config.DB_PATH.as_posix()}",
    echo=False,
    connect_args={"timeout": 30},
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from . import models  # noqa: F401  (register mappers)

    config.ensure_dirs()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # create_all 不会为已存在的表补列/补索引——这里做轻量迁移
        from sqlalchemy import text

        migrations = [
            "ALTER TABLE tasks ADD COLUMN options JSON",
            "ALTER TABLE novels ADD COLUMN subscribed BOOLEAN",
            "ALTER TABLE novels ADD COLUMN new_chapters INTEGER",
            "ALTER TABLE novels ADD COLUMN last_check_chapters INTEGER",
            "ALTER TABLE novels ADD COLUMN last_check_at DATETIME",
            "CREATE INDEX IF NOT EXISTS ix_media_title ON media (title)",
            "CREATE INDEX IF NOT EXISTS ix_media_source ON media (source_url)",
            "CREATE INDEX IF NOT EXISTS ix_notes_novel_chapter ON notes (novel_id, chapter_idx)",
        ]
        for stmt in migrations:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass  # 列/索引已存在
