"""按需 EPUB 生成（B2）：KOReader 等 OPDS 阅读器可直接下载 EPUB。

缓存策略：data/exports/<novel_id>.epub，小说 updated_at 未变化时直接复用；
生成在后台线程执行，写入临时文件后原子替换。
"""
from __future__ import annotations

import asyncio
import html
import os
import tempfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from .. import config
from ..database import SessionLocal
from ..models import Chapter, Novel

EXPORTS_DIR = config.DATA_DIR / "exports"


def _read_chapter_text(ch: Chapter) -> str:
    if ch.content:
        return ch.content
    if ch.content_path:
        p = config.DATA_DIR / ch.content_path
        if p.exists():
            return p.read_text(encoding="utf-8", errors="replace")
    return ""


def _chapter_xhtml(title: str, text: str) -> str:
    paras = "\n".join(
        f"<p>{html.escape(line.strip())}</p>"
        for line in text.splitlines() if line.strip()
    ) or "<p></p>"
    safe_title = html.escape(title or "")
    # 注意：不要加 <?xml?> 声明——ebooklib 0.20 的 get_body_content()
    # 遇到声明会解析出空 body，导致 write 阶段 "Document is empty"
    return (f"<html xmlns=\"http://www.w3.org/1999/xhtml\"><head><title>{safe_title}</title>"
            f"</head><body><h2>{safe_title}</h2>{paras}</body></html>")


def _build_sync(novel: Novel, chapters: list[Chapter], dest: Path) -> Path:
    from ebooklib import epub

    book = epub.EpubBook()
    book.set_identifier(f"moread-{novel.id}")
    book.set_title(novel.title or "未命名")
    book.set_language("zh")
    book.add_author(novel.author or "未知")

    spine: list = ["nav"]
    for ch in chapters:
        text = _read_chapter_text(ch)
        if not text.strip():
            continue
        item = epub.EpubHtml(
            title=ch.title or f"第{ch.idx + 1}章",
            file_name=f"chap_{ch.idx:05d}.xhtml",
            lang="zh",
        )
        item.content = _chapter_xhtml(ch.title or f"第{ch.idx + 1}章", text)
        book.add_item(item)
        book.toc.append(item)
        spine.append(item)
    if len(spine) <= 1:
        raise ValueError("novel has no readable chapters")
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    # 临时文件生成后原子替换，避免半成品缓存
    fd, tmp = tempfile.mkstemp(suffix=".epub", dir=str(dest.parent))
    os.close(fd)
    try:
        epub.write_epub(tmp, book)
        os.replace(tmp, dest)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass  # 清理失败不得掩盖 write/replace 的原始异常
    return dest


async def build_epub(novel_id: str) -> Path:
    """生成（或复用缓存的）EPUB，返回文件路径。无章节时抛 ValueError。"""
    async with SessionLocal() as db:
        novel = await db.get(Novel, novel_id)
        if novel is None:
            raise FileNotFoundError(novel_id)
        chapters = (await db.execute(
            select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.idx)
        )).scalars().all()

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = EXPORTS_DIR / f"{novel_id}.epub"
    updated = novel.updated_at or novel.created_at or datetime.now()
    if dest.exists() and dest.stat().st_mtime >= updated.timestamp():
        return dest
    return await asyncio.to_thread(_build_sync, novel, list(chapters), dest)
