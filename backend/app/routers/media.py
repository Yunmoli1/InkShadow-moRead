"""Media endpoints: list / detail / file serving (Range) / delete / batch import."""

import asyncio
import mimetypes
import re
import urllib.parse
import uuid

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select

from .. import config
from ..database import SessionLocal
from ..models import MediaItem
from ..schemas import MediaOut

router = APIRouter(prefix="/api/media", tags=["media"])


def _write_chunks(dest, chunks: list[bytes]) -> None:
    with open(dest, "wb") as fh:
        for c in chunks:
            fh.write(c)


def _media_out(m: MediaItem) -> MediaOut:
    return MediaOut(
        id=m.id, media_type=m.media_type, title=m.title, source_url=m.source_url,
        file_path=m.file_path, thumbnail_path=m.thumbnail_path, mime_type=m.mime_type,
        file_size=m.file_size, duration=m.duration,
        preview_url=f"/api/media/{m.id}/file",
        thumbnail_url=f"/api/media/{m.id}/thumb" if m.thumbnail_path else "",
        extra=m.extra or {},
        created_at=m.created_at,
    )


@router.get("")
async def list_media(
    page: int = Query(1, ge=1), page_size: int = Query(24, ge=1, le=100),
    media_type: str | None = Query(None, description="image/video/audio/page/doc"),
    search: str | None = None,
) -> dict:
    async with SessionLocal() as db:
        q = select(MediaItem)
        count_q = select(func.count(MediaItem.id))
        if media_type and media_type != "全部":
            cond = MediaItem.media_type == media_type
            q = q.where(cond)
            count_q = count_q.where(cond)
        if search:
            cond = MediaItem.title.contains(search) | MediaItem.source_url.contains(search)
            q = q.where(cond)
            count_q = count_q.where(cond)
        total = (await db.execute(count_q)).scalar() or 0
        rows = (await db.execute(
            q.order_by(MediaItem.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()
        return {"items": [_media_out(m) for m in rows], "total": total,
                "page": page, "page_size": page_size}


@router.post("/batch-import", response_model=dict, status_code=201)
async def batch_import(files: list[UploadFile] = File(...)) -> dict:
    kind_map = {
        ".jpg": "image", ".jpeg": "image", ".png": "image", ".gif": "image", ".webp": "image",
        ".bmp": "image", ".avif": "image", ".svg": "image",
        ".mp4": "video", ".mkv": "video", ".webm": "video", ".mov": "video", ".avi": "video",
        ".mp3": "audio", ".m4a": "audio", ".flac": "audio", ".wav": "audio", ".ogg": "audio", ".opus": "audio",
        ".html": "page", ".htm": "page", ".pdf": "doc",
    }
    imported, skipped = [], []
    async with SessionLocal() as db:
        for f in files[:200]:
            name = f.filename or "file"
            suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
            mtype = kind_map.get(suffix)
            if not mtype:
                skipped.append(name)
                continue
            rel_dir = config.MEDIA_DIR / "imports" / uuid.uuid4().hex[:8]
            rel_dir.mkdir(parents=True, exist_ok=True)
            safe_name = re.sub(r'[\\/:*?"<>|]', "_", name)
            dest = rel_dir / safe_name
            # 异步分块读取 + 线程池落盘，避免大文件阻塞事件循环
            chunks: list[bytes] = []
            while True:
                chunk = await f.read(1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            await asyncio.to_thread(_write_chunks, dest, chunks)
            db.add(MediaItem(
                media_type=mtype, title=name.rsplit(".", 1)[0],
                file_path=dest.relative_to(config.DATA_DIR).as_posix(),
                mime_type=mimetypes.guess_type(name)[0] or "application/octet-stream",
                file_size=dest.stat().st_size,
                extra={"imported": True},
            ))
            imported.append(name)
        await db.commit()
    return {"imported": imported, "skipped": skipped, "count": len(imported)}


@router.get("/{media_id}", response_model=MediaOut)
async def media_detail(media_id: str) -> MediaOut:
    async with SessionLocal() as db:
        m = await db.get(MediaItem, media_id)
        if m is None:
            raise HTTPException(404, "资源不存在")
        return _media_out(m)


@router.get("/{media_id}/thumb")
async def media_thumb(media_id: str):
    """缩略图（视频首帧 / 图片压缩版）；无缩略图时 404，前端回退原图。"""
    from fastapi.responses import FileResponse

    async with SessionLocal() as db:
        m = await db.get(MediaItem, media_id)
        if m is None or not m.thumbnail_path:
            raise HTTPException(404, "无缩略图")
        path = config.DATA_DIR / m.thumbnail_path
    if not path.is_file():
        raise HTTPException(404, "缩略图文件缺失")
    return FileResponse(path, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})


@router.patch("/{media_id}/progress")
async def media_progress(media_id: str, body: dict) -> dict:
    """记录/查询音视频播放进度（秒），存于 extra。"""
    from datetime import datetime, timezone

    position = float(body.get("position", 0))
    async with SessionLocal() as db:
        m = await db.get(MediaItem, media_id)
        if m is None:
            raise HTTPException(404, "资源不存在")
        extra = dict(m.extra or {})
        extra["progress"] = round(position, 1)
        extra["progress_at"] = datetime.now(timezone.utc).isoformat()
        m.extra = extra
        await db.commit()
    return {"id": media_id, "progress": extra["progress"], "message": "播放进度已保存"}


@router.post("/backfill-assets")
async def backfill_assets() -> dict:
    """为缺少时长/缩略图的既有资源补建（视频时长+首帧、图片缩略图）。"""
    import asyncio

    from ..services import media_assets

    async with SessionLocal() as db:
        items = (await db.execute(select(MediaItem))).scalars().all()
        updated = 0
        for m in items:
            try:
                if await media_assets.fill_media_assets(db, m):
                    updated += 1
            except Exception:
                continue
        await db.commit()
    return {"updated": updated, "message": f"已为 {updated} 个资源补建时长/缩略图"}


@router.get("/{media_id}/file")
async def media_file(media_id: str, request: Request) -> StreamingResponse:
    """Serve file bytes with HTTP Range support (video/audio seeking)."""
    async with SessionLocal() as db:
        m = await db.get(MediaItem, media_id)
        if m is None:
            raise HTTPException(404, "资源不存在")
        path = config.DATA_DIR / m.file_path
        if not path.is_file():
            raise HTTPException(410, "文件已被移动或删除")
        mime = m.mime_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    size = path.stat().st_size
    range_header = request.headers.get("range")
    start, end = 0, size - 1
    status_code = 200
    if range_header:
        m_ = re.match(r"bytes=(\d*)-(\d*)", range_header)
        if m_:
            if m_.group(1):
                start = int(m_.group(1))
                end = int(m_.group(2)) if m_.group(2) else min(start + 4 * 1024 * 1024 - 1, size - 1)
            else:
                start = max(0, size - int(m_.group(2)))
            status_code = 206
    length = end - start + 1

    async def file_iter():
        with open(path, "rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(256 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        # RFC 5987: non-ASCII (中文/emoji) filenames must go in filename*,
        # plain filename* requires latin-1 and crashes the response.
        "Content-Disposition": _content_disposition(path.name),
    }
    if status_code == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return StreamingResponse(file_iter(), status_code=status_code, media_type=mime, headers=headers)


def _content_disposition(filename: str) -> str:
    """Build a header-safe Content-Disposition for any filename."""
    ascii_name = filename.encode("ascii", "ignore").decode() or "file"
    quoted = urllib.parse.quote(filename)
    return f"inline; filename=\"{ascii_name}\"; filename*=UTF-8''{quoted}"


@router.post("/{media_id}/extract-article")
async def extract_article_from_media(media_id: str) -> dict:
    """把已归档网页（page 类型）的正文提取为"文章"入书架，返回小说信息。"""
    import asyncio

    from ..models import Novel
    from ..services.article_extractor import extract_article
    from ..services.novel_parser import import_article

    async with SessionLocal() as db:
        m = await db.get(MediaItem, media_id)
        if m is None:
            raise HTTPException(404, "资源不存在")
        if m.media_type not in ("page", "doc"):
            raise HTTPException(400, "仅网页归档可提取正文")
        path = config.DATA_DIR / m.file_path
        url = m.source_url
    if not path.is_file():
        raise HTTPException(410, "归档文件已被移动或删除")

    def _extract():
        raw = path.read_bytes()
        for enc in ("utf-8", "gb18030", "big5"):
            try:
                return extract_article(raw.decode(enc))
            except UnicodeDecodeError:
                continue
        return extract_article(raw.decode("utf-8", errors="replace"))

    article = await asyncio.to_thread(_extract)
    if not article:
        raise HTTPException(422, "未能提取出有效正文（页面可能是导航页或需要 JS 渲染）")
    novel = await import_article(title=article["title"], text=article["text"], source_url=url)
    return {"novel_id": novel.id, "title": novel.title,
            "chars": len(article["text"]),
            "message": f"已提取正文《{novel.title}》到书架（文章分类）"}


@router.delete("/{media_id}")
async def delete_media(media_id: str, delete_file: bool = True) -> dict:
    async with SessionLocal() as db:
        m = await db.get(MediaItem, media_id)
        if m is None:
            raise HTTPException(404, "资源不存在")
        path = config.DATA_DIR / m.file_path
        await db.delete(m)
        await db.commit()
    if delete_file and path.is_file():
        try:
            path.unlink()
            parent = path.parent
            if parent != config.DATA_DIR and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass
    return {"id": media_id, "message": "资源已删除"}


@router.get("/types/summary")
async def types_summary() -> dict:
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(MediaItem.media_type, func.count(MediaItem.id)).group_by(MediaItem.media_type)
        )).all()
        return {t: c for t, c in rows}
