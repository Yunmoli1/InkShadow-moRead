"""Novel endpoints: shelf, chapters, notes, progress, stats, AI summary, import."""

import json
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from sqlalchemy import delete, func, select

from ..database import SessionLocal
from ..models import AiSummary, Chapter, Note, Novel, ReadingSession, Setting
from ..schemas import (
    AiSummaryIn, AiSummaryOut, ChapterContentOut, ChapterOut, ImportResult,
    NoteIn, NoteOut, NovelOut, ProgressIn, ReadingSessionIn,
)
from ..services.ai_service import AiError, stream_summarize, summarize
from ..services.novel_parser import import_novel_file
from .. import config

router = APIRouter(prefix="/api/novels", tags=["novels"])


def _novel_out(n: Novel) -> NovelOut:
    return NovelOut(
        id=n.id, title=n.title, author=n.author, source_url=n.source_url,
        description=n.description, cover_path=n.cover_path, file_type=n.file_type,
        category=n.category, total_chapters=n.total_chapters, read_chapters=n.read_chapters,
        last_chapter_idx=n.last_chapter_idx, last_scroll_pos=n.last_scroll_pos,
        file_size=n.file_size, subscribed=bool(n.subscribed), new_chapters=n.new_chapters or 0,
        tags=n.tags or [],
        created_at=n.created_at, updated_at=n.updated_at,
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


@router.get("")
async def list_novels(
    page: int = Query(1, ge=1), page_size: int = Query(24, ge=1, le=100),
    search: str | None = None, category: str | None = None, tag: str | None = None,
) -> dict:
    async with SessionLocal() as db:
        q = select(Novel)
        count_q = select(func.count(Novel.id))
        if search:
            like = f"%{search}%"
            cond = Novel.title.like(like) | Novel.author.like(like)
            q = q.where(cond)
            count_q = count_q.where(cond)
        if category and category != "全部":
            q = q.where(Novel.category == category)
            count_q = count_q.where(Novel.category == category)
        if tag:
            # tags 是 JSON 数组；SQLAlchemy 默认 ensure_ascii 序列化（中文存为 \uXXXX），
            # 用 json.dumps(tag) 生成带引号的转义串做 LIKE，兼容任意字符
            needle = json.dumps(tag.replace('"', ""))
            cond = Novel.tags.like(f"%{needle}%")
            q = q.where(cond)
            count_q = count_q.where(cond)
        total = (await db.execute(count_q)).scalar() or 0
        rows = (await db.execute(
            q.order_by(Novel.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()
        return {"items": [_novel_out(n) for n in rows], "total": total,
                "page": page, "page_size": page_size}


@router.get("/tag-list")
async def novel_tag_list() -> list[dict]:
    """全部标签及数量（B1 标签筛选数据源）。"""
    async with SessionLocal() as db:
        rows = (await db.execute(select(Novel.tags))).scalars().all()
    counter: dict[str, int] = {}
    for tags in rows:
        for t in tags or []:
            if isinstance(t, str) and t:
                counter[t] = counter.get(t, 0) + 1
    return [{"tag": t, "count": c} for t, c in
            sorted(counter.items(), key=lambda kv: -kv[1])[:50]]


@router.get("/{novel_id}/download.epub")
async def download_epub(novel_id: str):
    """按需生成并下载整本书 EPUB（B2，OPDS acquisition 目标）。

    带缓存的同步生成在后台线程执行；无章节返回 404。
    """
    from fastapi.responses import FileResponse

    from ..services.epub_export import build_epub

    try:
        path = await build_epub(novel_id)
    except FileNotFoundError:
        raise HTTPException(404, "小说不存在")
    except ValueError as exc:
        raise HTTPException(404, str(exc) or "无章节内容")

    async with SessionLocal() as db:
        n = await db.get(Novel, novel_id)
    title = (n.title if n else "book") or "book"
    return FileResponse(path, media_type="application/epub+zip", filename=f"{title}.epub")


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
        chunks = []
        while chunk := await f.read(1024 * 1024):
            chunks.append(chunk)
        import asyncio

        def _flush() -> None:
            with open(tmp, "wb") as fh:
                for c in chunks:
                    fh.write(c)

        await asyncio.to_thread(_flush)
        try:
            original_stem = f.filename.rsplit(".", 1)[0] if f.filename else None
            novel = await import_novel_file(tmp, fallback_title=original_stem)
            result.imported.append(novel.title)
            # 后台 AI 自动标签（失败静默）
            import asyncio as _aio

            from ..services.tagger import tag_novel

            _aio.get_running_loop().create_task(_safe_tag(novel.id, tag_novel))
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


@router.get("/{novel_id}/images/{name}")
async def novel_image(novel_id: str, name: str):
    """Serve an image extracted from an imported EPUB ([img:<name>] markers)."""
    import re

    from fastapi.responses import FileResponse

    if not re.fullmatch(r"[\w.\-]+", name):
        raise HTTPException(400, "非法文件名")
    p = config.COVERS_DIR / novel_id / "images" / name
    if not p.is_file():
        raise HTTPException(404, "图片不存在")
    mime = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
        ".bmp": "image/bmp",
    }.get(p.suffix.lower(), "application/octet-stream")
    return FileResponse(p, media_type=mime)


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


@router.get("/{novel_id}/search")
async def search_in_novel(novel_id: str, q: str = Query(..., min_length=1, max_length=100)) -> dict:
    """书内全文搜索：标题与正文（含磁盘文件章节），返回带上下文片段的命中。"""
    ql = q.strip().lower()
    if not ql:
        return {"query": q, "results": []}
    async with SessionLocal() as db:
        if await db.get(Novel, novel_id) is None:
            raise HTTPException(404, "小说不存在")
        rows = (await db.execute(
            select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.idx)
        )).scalars().all()
    results = []
    for c in rows:
        content = c.content
        if not content and c.content_path:
            p = config.DATA_DIR / c.content_path
            if p.exists():
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    content = ""
        hits = []
        if ql in c.title.lower():
            hits.append({"where": "title", "snippet": c.title[:80]})
        hay = content.lower()
        start = 0
        while len(hits) < 4:
            pos = hay.find(ql, start)
            if pos < 0:
                break
            s = max(0, pos - 25)
            e = min(len(content), pos + len(ql) + 45)
            snippet = content[s:e].replace("\n", " ")
            hits.append({"where": "content",
                         "snippet": ("…" if s > 0 else "") + snippet + ("…" if e < len(content) else "")})
            start = pos + len(ql)
        if hits:
            results.append({"chapter_id": c.id, "chapter_idx": c.idx, "title": c.title, "hits": hits})
        if len(results) >= 50:
            break
    return {"query": q, "results": results, "truncated": len(results) >= 50}


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


@router.post("/{novel_id}/ai-summary/stream")
async def ai_summary_stream(novel_id: str, body: AiSummaryIn):
    """流式 AI 摘要（SSE）：delta 增量 / end 完成 / error 友好错误。"""
    import json

    from fastapi.responses import StreamingResponse

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
        cached_summary = cached.summary if cached else None
        content = ""
        if cached_summary is None:
            content = c.content
            if not content and c.content_path:
                p = config.DATA_DIR / c.content_path
                content = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
            if not content.strip():
                raise HTTPException(400, "章节内容为空，无法生成摘要")
        chapter_idx = c.idx
        chapter_id = body.chapter_id

    async def gen():
        if cached_summary is not None:
            yield f"event: delta\ndata: {json.dumps({'text': cached_summary}, ensure_ascii=False)}\n\n"
            yield f"event: end\ndata: {json.dumps({'summary': cached_summary, 'cached': True}, ensure_ascii=False)}\n\n"
            return
        buf = ""
        try:
            async for delta in stream_summarize(content, settings):
                buf += delta
                yield f"event: delta\ndata: {json.dumps({'text': delta}, ensure_ascii=False)}\n\n"
        except AiError as exc:
            if buf:
                yield f"event: end\ndata: {json.dumps({'summary': buf, 'cached': False}, ensure_ascii=False)}\n\n"
            else:
                yield f"event: error\ndata: {json.dumps({'message': str(exc)}, ensure_ascii=False)}\n\n"
            return
        if not buf.strip():
            yield f"event: error\ndata: {json.dumps({'message': 'AI 未返回内容，请检查模型是否可用。'}, ensure_ascii=False)}\n\n"
            return
        async with SessionLocal() as db2:
            db2.add(AiSummary(novel_id=novel_id, chapter_id=chapter_id,
                              chapter_idx=chapter_idx, summary=buf,
                              model=str(settings.get("ai_model") or "llama3")))
            await db2.commit()
        yield f"event: end\ndata: {json.dumps({'summary': buf, 'cached': False}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class SubscribeIn(BaseModel):
    subscribed: bool


@router.patch("/{novel_id}/subscribe")
async def subscribe_novel(novel_id: str, body: SubscribeIn) -> dict:
    async with SessionLocal() as db:
        n = await db.get(Novel, novel_id)
        if n is None:
            raise HTTPException(404, "小说不存在")
        n.subscribed = body.subscribed
        if not body.subscribed:
            n.new_chapters = 0
        await db.commit()
    return {"id": novel_id, "subscribed": body.subscribed,
            "message": "已开启追更（每 6 小时自动检查）" if body.subscribed else "已关闭追更"}


class SwitchSourceIn(BaseModel):
    new_url: str = Field(min_length=8, max_length=2048)


@router.post("/{novel_id}/switch-source")
async def switch_source(novel_id: str, body: SwitchSourceIn) -> dict:
    """一键换源：用新镜像 URL 重新增量抓取，完成后自动重建章节并更新来源。"""
    from ..services import tool_registry
    from ..services.task_manager import manager

    async with SessionLocal() as db:
        n = await db.get(Novel, novel_id)
        if n is None:
            raise HTTPException(404, "小说不存在")
        if n.source_url and n.source_url.rstrip("/") == body.new_url.rstrip("/"):
            raise HTTPException(400, "新来源与当前来源相同")
        title = n.title
    spec = tool_registry.get_spec("lncrawl")
    if spec is None or not tool_registry.resolve_executable(spec):
        raise HTTPException(400, "lncrawl 未安装，无法换源")
    task = await manager.create_task(
        tool="lncrawl", url=body.new_url, options={"format": "txt", "switch_novel_id": novel_id},
        dest_type="novel", title=f"换源：{title}",
    )
    return {"task_id": task.id,
            "message": "换源任务已创建（增量下载，完成后自动重建章节并更新来源）"}


async def _safe_tag(novel_id: str, fn) -> None:
    try:
        await fn(novel_id)
    except Exception:
        pass


@router.post("/auto-tag")
async def novels_auto_tag() -> dict:
    """为还没有标签的书生成 AI 标签（需本地 Ollama / 外部 AI 可用）。"""
    import asyncio

    from ..models import Novel
    from ..services.tagger import tag_novel

    async with SessionLocal() as db:
        rows = (await db.execute(select(Novel.id).where(Novel.category != "文章"))).scalars().all()
        targets = [r for r in rows if r]
    # 取全部书再过滤无标签的
    async with SessionLocal() as db:
        rows = (await db.execute(select(Novel))).scalars().all()
        targets = [n.id for n in rows if not n.tags]
    done = 0
    for nid in targets[:50]:
        tags = await tag_novel(nid)
        if tags:
            done += 1
    return {"tagged": done, "message": f"已为 {done} 本书生成标签"}


@router.post("/{novel_id}/check-update")
async def check_novel_update(novel_id: str) -> dict:
    from ..services.updater import check_novel

    try:
        return await check_novel(novel_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/check-updates")
async def check_all_updates() -> dict:
    """检查所有订阅书（跳过 6 小时内已检查的）。"""
    from ..services.updater import check_all

    return await check_all(reason="manual")


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
