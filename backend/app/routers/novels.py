"""Novel endpoints: shelf, chapters, notes, progress, stats, AI summary, import."""

import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from sqlalchemy import delete, func, select

from ..database import SessionLocal
from ..models import AiSummary, Chapter, Note, Novel, ReadingSession, Setting
from ..schemas import (
    AiSummaryIn, AiSummaryOut, ChapterContentOut, ChapterOut, ImportResult,
    NoteIn, NoteOut, NovelOut, ProgressIn, ReadingSessionIn,
)
from ..services.ai_service import AiError, summarize
from ..services.novel_parser import import_novel_file
from .. import config

router = APIRouter(prefix="/api/novels", tags=["novels"])


def _novel_out(n: Novel) -> NovelOut:
    return NovelOut(
        id=n.id, title=n.title, author=n.author, source_url=n.source_url,
        description=n.description, cover_path=n.cover_path, file_type=n.file_type,
        category=n.category, total_chapters=n.total_chapters, read_chapters=n.read_chapters,
        last_chapter_idx=n.last_chapter_idx, last_scroll_pos=n.last_scroll_pos,
        file_size=n.file_size, created_at=n.created_at, updated_at=n.updated_at,
    )


# NOTE: /stats must be declared before /{id}
@router.get("/stats")
async def reading_stats() -> dict:
    async with SessionLocal() as db:
        total_novels = (await db.execute(select(func.count(Novel.id)))).scalar() or 0
        total_chapters = (await db.execute(select(func.coalesce(func.sum(Novel.total_chapters), 0)))).scalar() or 0
        read_chapters = (await db.execute(select(func.coalesce(func.sum(Novel.read_chapters), 0)))).scalar() or 0
        total_seconds = (await db.execute(select(func.coalesce(func.sum(ReadingSession.duration_sec), 0)))).scalar() or 0
        notes_count = (await db.execute(select(func.count(Note.id)))).scalar() or 0
        # daily trend: last 30 days
        since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        rows = (await db.execute(
            select(ReadingSession.day, func.sum(ReadingSession.duration_sec), func.sum(ReadingSession.chapters_read))
            .where(ReadingSession.day >= since)
            .group_by(ReadingSession.day)
            .order_by(ReadingSession.day)
        )).all()
        daily = [{"day": d, "minutes": round((s or 0) / 60, 1), "chapters": c or 0} for d, s, c in rows]
        top = (await db.execute(
            select(Novel.id, Novel.title, func.sum(ReadingSession.duration_sec))
            .join(ReadingSession, ReadingSession.novel_id == Novel.id)
            .group_by(Novel.id, Novel.title)
            .order_by(func.sum(ReadingSession.duration_sec).desc())
            .limit(5)
        )).all()
        year = datetime.now(timezone.utc).year
        year_seconds = (await db.execute(
            select(func.coalesce(func.sum(ReadingSession.duration_sec), 0))
            .where(ReadingSession.day >= f"{year}-01-01")
        )).scalar() or 0
        return {
            "total_novels": total_novels,
            "total_chapters": total_chapters,
            "read_chapters": read_chapters,
            "total_minutes": round(total_seconds / 60, 1),
            "year_minutes": round(year_seconds / 60, 1),
            "notes_count": notes_count,
            "daily": daily,
            "top_novels": [{"id": i, "title": t, "minutes": round((s or 0) / 60, 1)} for i, t, s in top],
        }


@router.get("", response_model=list[NovelOut])
async def list_novels(
    page: int = Query(1, ge=1), page_size: int = Query(24, ge=1, le=100),
    search: str | None = None, category: str | None = None,
) -> list[NovelOut]:
    async with SessionLocal() as db:
        q = select(Novel)
        if search:
            q = q.where(Novel.title.contains(search) | Novel.author.contains(search))
        if category and category != "全部":
            q = q.where(Novel.category == category)
        rows = (await db.execute(
            q.order_by(Novel.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()
        return [_novel_out(n) for n in rows]


@router.post("/import", response_model=ImportResult)
async def import_novels(files: list[UploadFile] = File(...)) -> ImportResult:
    """批量导入本地小说文件（TXT/EPUB）。"""
    result = ImportResult(imported=[], skipped=[], errors=[])
    for f in files[:50]:
        suffix = "." + f.filename.rsplit(".", 1)[-1].lower() if f.filename and "." in f.filename else ""
        if suffix not in (".txt", ".epub"):
            result.skipped.append(f.filename or "未命名")
            continue
        tmp = config.DOWNLOADS_DIR / f"import_{uuid.uuid4().hex[:8]}_{f.filename}"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "wb") as fh:
            while chunk := await f.read(1024 * 1024):
                fh.write(chunk)
        try:
            original_stem = f.filename.rsplit(".", 1)[0] if f.filename else None
            novel = await import_novel_file(tmp, fallback_title=original_stem)
            result.imported.append(novel.title)
        except Exception as exc:
            result.errors.append(f"{f.filename}: {exc}")
        finally:
            tmp.unlink(missing_ok=True)
    if not result.imported and result.skipped and not result.errors:
        result.errors.append("没有可导入的文件（仅支持 TXT/EPUB）")
    return result


@router.get("/{novel_id}", response_model=NovelOut)
async def get_novel(novel_id: str) -> NovelOut:
    async with SessionLocal() as db:
        n = await db.get(Novel, novel_id)
        if n is None:
            raise HTTPException(404, "小说不存在")
        return _novel_out(n)


@router.get("/{novel_id}/chapters")
async def list_chapters(
    novel_id: str, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
) -> dict:
    """分页章节列表（配合前端 react-window 虚拟滚动）。"""
    async with SessionLocal() as db:
        n = await db.get(Novel, novel_id)
        if n is None:
            raise HTTPException(404, "小说不存在")
        total = (await db.execute(
            select(func.count(Chapter.id)).where(Chapter.novel_id == novel_id)
        )).scalar() or 0
        rows = (await db.execute(
            select(Chapter).where(Chapter.novel_id == novel_id)
            .order_by(Chapter.idx).offset(offset).limit(limit)
        )).scalars().all()
        return {
            "total": total, "offset": offset, "limit": limit,
            "items": [
                {"id": c.id, "idx": c.idx, "title": c.title, "word_count": c.word_count}
                for c in rows
            ],
        }


@router.get("/{novel_id}/chapters/{chapter_id}/content", response_model=ChapterContentOut)
async def chapter_content(novel_id: str, chapter_id: str) -> ChapterContentOut:
    async with SessionLocal() as db:
        c = await db.get(Chapter, chapter_id)
        if c is None or c.novel_id != novel_id:
            raise HTTPException(404, "章节不存在")
        content = c.content
        if not content and c.content_path:
            p = config.DATA_DIR / c.content_path
            if p.exists():
                content = p.read_text(encoding="utf-8", errors="replace")
        return ChapterContentOut(
            id=c.id, idx=c.idx, title=c.title, content=content,
            word_count=c.word_count, novel_id=novel_id,
        )


@router.delete("/{novel_id}")
async def delete_novel(novel_id: str) -> dict:
    async with SessionLocal() as db:
        n = await db.get(Novel, novel_id)
        if n is None:
            raise HTTPException(404, "小说不存在")
        await db.execute(delete(Note).where(Note.novel_id == novel_id))
        await db.execute(delete(ReadingSession).where(ReadingSession.novel_id == novel_id))
        await db.execute(delete(AiSummary).where(AiSummary.novel_id == novel_id))
        await db.execute(delete(Chapter).where(Chapter.novel_id == novel_id))
        await db.delete(n)
        await db.commit()
    return {"id": novel_id, "message": "已删除小说及其章节/笔记"}


@router.patch("/{novel_id}/progress")
async def update_progress(novel_id: str, body: ProgressIn) -> dict:
    async with SessionLocal() as db:
        n = await db.get(Novel, novel_id)
        if n is None:
            raise HTTPException(404, "小说不存在")
        n.last_chapter_idx = max(n.last_chapter_idx, body.chapter_idx)
        n.last_scroll_pos = body.scroll_pos
        n.read_chapters = max(n.read_chapters, min(body.chapter_idx + 1, n.total_chapters))
        n.updated_at = datetime.now(timezone.utc)
        if body.duration_sec > 0:
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            session = ReadingSession(
                novel_id=novel_id, duration_sec=body.duration_sec,
                chapters_read=body.chapters_read, day=day,
            )
            db.add(session)
        await db.commit()
        return {
            "id": novel_id, "last_chapter_idx": n.last_chapter_idx,
            "read_chapters": n.read_chapters, "message": "进度已保存",
        }


@router.post("/{novel_id}/notes", response_model=NoteOut, status_code=201)
async def create_note(novel_id: str, body: NoteIn) -> NoteOut:
    async with SessionLocal() as db:
        n = await db.get(Novel, novel_id)
        if n is None:
            raise HTTPException(404, "小说不存在")
        note = Note(
            novel_id=novel_id, chapter_id=body.chapter_id,
            chapter_title=body.chapter_title, chapter_idx=body.chapter_idx,
            excerpt=body.excerpt, content=body.content,
        )
        db.add(note)
        await db.commit()
        await db.refresh(note)
        return NoteOut(
            id=note.id, novel_id=note.novel_id, chapter_id=note.chapter_id,
            chapter_title=note.chapter_title, chapter_idx=note.chapter_idx,
            excerpt=note.excerpt, content=note.content, created_at=note.created_at,
        )


@router.get("/{novel_id}/notes", response_model=list[NoteOut])
async def list_notes(novel_id: str, chapter_idx: int | None = None) -> list[NoteOut]:
    async with SessionLocal() as db:
        q = select(Note).where(Note.novel_id == novel_id)
        if chapter_idx is not None:
            q = q.where(Note.chapter_idx == chapter_idx)
        rows = (await db.execute(q.order_by(Note.created_at.desc()))).scalars().all()
        return [
            NoteOut(id=t.id, novel_id=t.novel_id, chapter_id=t.chapter_id,
                    chapter_title=t.chapter_title, chapter_idx=t.chapter_idx,
                    excerpt=t.excerpt, content=t.content, created_at=t.created_at)
            for t in rows
        ]


@router.delete("/{novel_id}/notes/{note_id}")
async def delete_note(novel_id: str, note_id: str) -> dict:
    async with SessionLocal() as db:
        note = await db.get(Note, note_id)
        if note is None or note.novel_id != novel_id:
            raise HTTPException(404, "笔记不存在")
        await db.delete(note)
        await db.commit()
    return {"id": note_id, "message": "笔记已删除"}


@router.post("/{novel_id}/ai-summary", response_model=AiSummaryOut)
async def ai_summary(novel_id: str, body: AiSummaryIn) -> AiSummaryOut:
    async with SessionLocal() as db:
        c = await db.get(Chapter, body.chapter_id)
        if c is None or c.novel_id != novel_id:
            raise HTTPException(404, "章节不存在")
        cached = await db.scalar(
            select(AiSummary).where(
                AiSummary.novel_id == novel_id, AiSummary.chapter_id == body.chapter_id
            )
        )
        settings_rows = (await db.execute(select(Setting))).scalars().all()
        settings = {s.key: s.value for s in settings_rows}
        if cached:
            return AiSummaryOut(novel_id=novel_id, chapter_id=body.chapter_id,
                                summary=cached.summary, model=cached.model, cached=True)
        content = c.content
        if not content and c.content_path:
            p = config.DATA_DIR / c.content_path
            content = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        if not content.strip():
            raise HTTPException(400, "章节内容为空，无法生成摘要")
        try:
            summary = await summarize(content, settings)
        except AiError as exc:
            raise HTTPException(503, str(exc))
        row = AiSummary(novel_id=novel_id, chapter_id=body.chapter_id,
                        chapter_idx=c.idx, summary=summary,
                        model=str(settings.get("ai_model") or "llama3"))
        db.add(row)
        await db.commit()
        return AiSummaryOut(novel_id=novel_id, chapter_id=body.chapter_id,
                            summary=summary, model=row.model, cached=False)


@router.post("/{novel_id}/reading-session")
async def log_reading_session(novel_id: str, body: ReadingSessionIn) -> dict:
    async with SessionLocal() as db:
        n = await db.get(Novel, novel_id)
        if n is None:
            raise HTTPException(404, "小说不存在")
        db.add(ReadingSession(
            novel_id=novel_id, duration_sec=body.duration_sec,
            chapters_read=body.chapters_read,
            day=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        ))
        await db.commit()
    return {"message": "阅读记录已保存"}
