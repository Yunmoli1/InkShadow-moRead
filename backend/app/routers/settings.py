"""Settings / storage / backup / global search endpoints."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select

from .. import config
from ..database import SessionLocal
from ..models import Chapter, MediaItem, Note, Novel, Setting
from ..schemas import SearchAllOut, SettingsIn, SettingsOut
from ..services import storage as storage_svc

router = APIRouter(prefix="/api", tags=["settings"])

DEFAULTS = {
    "theme": "light",
    "ai_base_url": config.DEFAULT_AI_BASE_URL,
    "ai_model": config.DEFAULT_AI_MODEL,
    "ai_style": "ollama",
    "ai_api_key": "",
    "storage_quota_gb": config.DEFAULT_STORAGE_QUOTA_GB,
    "reader_font_size": 18,
    "reader_line_height": 1.8,
    "reader_paper": "paper",
    "reader_mode": "scroll",
}


async def _load_settings(db) -> dict:
    rows = (await db.execute(select(Setting))).scalars().all()
    data = dict(DEFAULTS)
    for row in rows:
        data[row.key] = row.value
    return data


@router.get("/settings", response_model=SettingsOut)
async def get_settings() -> SettingsOut:
    async with SessionLocal() as db:
        data = await _load_settings(db)
    return SettingsOut(**{k: data.get(k, v) for k, v in DEFAULTS.items()})


@router.put("/settings", response_model=SettingsOut)
async def update_settings(body: SettingsIn) -> SettingsOut:
    async with SessionLocal() as db:
        updates = body.model_dump(exclude_none=True)
        for key, value in updates.items():
            row = await db.get(Setting, key)
            if row:
                row.value = value
            else:
                db.add(Setting(key=key, value=value))
        await db.commit()
        data = await _load_settings(db)
    return SettingsOut(**{k: data.get(k, v) for k, v in DEFAULTS.items()})


@router.get("/storage/stats")
async def storage_stats() -> dict:
    async with SessionLocal() as db:
        data = await _load_settings(db)
    return storage_svc.storage_stats(float(data["storage_quota_gb"]))


@router.post("/storage/cleanup")
async def storage_cleanup(older_than_days: int = 30) -> dict:
    """删除超过 N 天的已完成下载目录（书库与媒体库不受影响）。"""
    candidates = storage_svc.cleanup_candidates(older_than_days)
    count, freed = storage_svc.apply_cleanup(candidates)
    return {"removed": count, "freed_bytes": freed, "message": f"已清理 {count} 个过期下载目录，释放 {freed / 1024 / 1024:.1f} MB"}


# ---------------------------------------------------------------------------
# Backup export / import (encryption is applied client-side via WebCrypto)
# ---------------------------------------------------------------------------

@router.get("/backup/export")
async def backup_export() -> FileResponse:
    async with SessionLocal() as db:
        novels = (await db.execute(select(Novel))).scalars().all()
        chapters = (await db.execute(select(Chapter))).scalars().all()
        notes = (await db.execute(select(Note))).scalars().all()
        settings_rows = (await db.execute(select(Setting))).scalars().all()
        media = (await db.execute(select(MediaItem))).scalars().all()
        payload = {
            "app": "MoRead", "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "novels": [
                {
                    "id": n.id, "title": n.title, "author": n.author,
                    "source_url": n.source_url, "description": n.description,
                    "file_type": n.file_type, "category": n.category,
                    "total_chapters": n.total_chapters, "read_chapters": n.read_chapters,
                    "last_chapter_idx": n.last_chapter_idx, "last_scroll_pos": n.last_scroll_pos,
                    "chapters": [
                        {"idx": c.idx, "title": c.title, "content": c.content}
                        for c in chapters if c.novel_id == n.id
                    ],
                }
                for n in novels
            ],
            "notes": [
                {"novel_id": t.novel_id, "chapter_id": t.chapter_id, "chapter_title": t.chapter_title,
                 "chapter_idx": t.chapter_idx, "excerpt": t.excerpt, "content": t.content}
                for t in notes
            ],
            "media_meta": [
                {"media_type": m.media_type, "title": m.title, "source_url": m.source_url,
                 "mime_type": m.mime_type, "file_size": m.file_size}
                for m in media
            ],
            "settings": {s.key: s.value for s in settings_rows},
        }
    out = config.BACKUPS_DIR / f"moread-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return FileResponse(out, media_type="application/json", filename=out.name)


@router.post("/backup/import")
async def backup_import(request_bytes: dict) -> dict:
    """Accept decrypted backup JSON: {"app":"MoRead", "novels":[...], "notes":[...]}."""
    if request_bytes.get("app") != "MoRead":
        raise HTTPException(400, "不是有效的墨读备份文件")
    restored_novels = restored_notes = 0
    async with SessionLocal() as db:
        for n in request_bytes.get("novels", []):
            exists = await db.scalar(select(Novel).where(Novel.title == n.get("title", ""), Novel.author == n.get("author", "")))
            if exists:
                continue
            novel = Novel(
                title=n.get("title", "未命名"), author=n.get("author", ""),
                source_url=n.get("source_url", ""), description=n.get("description", ""),
                file_type=n.get("file_type", "txt"), category=n.get("category", "未分类"),
                total_chapters=n.get("total_chapters", 0), read_chapters=n.get("read_chapters", 0),
                last_chapter_idx=n.get("last_chapter_idx", 0), last_scroll_pos=n.get("last_scroll_pos", 0),
            )
            db.add(novel)
            await db.flush()
            for c in n.get("chapters", []):
                db.add(Chapter(novel_id=novel.id, idx=c.get("idx", 0),
                               title=c.get("title", ""), content=c.get("content", ""),
                               word_count=len(c.get("content", ""))))
            novel.total_chapters = len(n.get("chapters", []))
            restored_novels += 1
        for t in request_bytes.get("notes", []):
            if not await db.get(Novel, t.get("novel_id", "")):
                continue
            db.add(Note(novel_id=t["novel_id"], chapter_id=t.get("chapter_id"),
                        chapter_title=t.get("chapter_title", ""), chapter_idx=t.get("chapter_idx", 0),
                        excerpt=t.get("excerpt", ""), content=t.get("content", "")))
            restored_notes += 1
        for key, value in (request_bytes.get("settings") or {}).items():
            row = await db.get(Setting, key)
            if row:
                row.value = value
            else:
                db.add(Setting(key=key, value=value))
        await db.commit()
    return {"restored_novels": restored_novels, "restored_notes": restored_notes,
            "message": f"已恢复 {restored_novels} 本小说与 {restored_notes} 条笔记"}


# ---------------------------------------------------------------------------
# Global search (Ctrl+K)
# ---------------------------------------------------------------------------

@router.get("/search", response_model=SearchAllOut)
async def global_search(q: str) -> SearchAllOut:
    if not q.strip():
        return SearchAllOut(novels=[], media=[])
    async with SessionLocal() as db:
        like = f"%{q.strip()}%"
        novels = (await db.execute(
            select(Novel).where(or_(Novel.title.like(like), Novel.author.like(like))).limit(10)
        )).scalars().all()
        media = (await db.execute(
            select(MediaItem).where(or_(MediaItem.title.like(like), MediaItem.source_url.like(like))).limit(10)
        )).scalars().all()
        chapters = (await db.execute(
            select(Chapter.novel_id, func.count(Chapter.id))
            .where(Chapter.title.like(like)).group_by(Chapter.novel_id).limit(5)
        )).all()
    return SearchAllOut(
        novels=[{"id": n.id, "type": "novel", "title": n.title, "author": n.author} for n in novels]
        + [{"id": nid, "type": "chapter", "title": f"{cnt} 个匹配章节"} for nid, cnt in chapters],
        media=[{"id": m.id, "type": m.media_type, "title": m.title} for m in media],
    )
