"""Media endpoints: list / detail / file serving (Range) / delete / batch import."""

import mimetypes
import os
import re
import uuid

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select

from .. import config
from ..database import SessionLocal
from ..models import MediaItem
from ..schemas import MediaOut

router = APIRouter(prefix="/api/media", tags=["media"])


def _media_out(m: MediaItem) -> MediaOut:
    return MediaOut(
        id=m.id, media_type=m.media_type, title=m.title, source_url=m.source_url,
        file_path=m.file_path, thumbnail_path=m.thumbnail_path, mime_type=m.mime_type,
        file_size=m.file_size, duration=m.duration,
        preview_url=f"/api/media/{m.id}/file", extra=m.extra or {},
        created_at=m.created_at,
    )


@router.get("", response_model=list[MediaOut])
async def list_media(
    page: int = Query(1, ge=1), page_size: int = Query(24, ge=1, le=100),
    media_type: str | None = Query(None, description="image/video/audio/page/doc"),
    search: str | None = None,
) -> list[MediaOut]:
    async with SessionLocal() as db:
        q = select(MediaItem)
        if media_type and media_type != "全部":
            if media_type == "page":
                q = q.where(MediaItem.media_type == "page")
            else:
                q = q.where(MediaItem.media_type == media_type)
        if search:
            q = q.where(MediaItem.title.contains(search) | MediaItem.source_url.contains(search))
        rows = (await db.execute(
            q.order_by(MediaItem.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()
        return [_media_out(m) for m in rows]


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
            with open(dest, "wb") as fh:
                while chunk := await f.read(1024 * 1024):
                    fh.write(chunk)
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
        "Content-Disposition": f'inline; filename="{os.path.basename(path.name)}"',
    }
    if status_code == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return StreamingResponse(file_iter(), status_code=status_code, media_type=mime, headers=headers)


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
