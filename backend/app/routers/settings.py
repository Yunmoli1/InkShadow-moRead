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
    "proxy_url": config.DEFAULT_PROXY_URL,
    "storage_quota_gb": config.DEFAULT_STORAGE_QUOTA_GB,
    "reader_font_size": 18,
    "reader_line_height": 1.8,
    "reader_paper": "paper",
    "reader_mode": "scroll",
    "access_token": "",
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
        if "access_token" in updates:
            from ..services.token_guard import invalidate
            invalidate()
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
    """v2 完整备份：正文（含大书的磁盘文件内容）、封面、EPUB 图片全部内联。"""
    import base64

    async with SessionLocal() as db:
        novels = (await db.execute(select(Novel))).scalars().all()
        chapters = (await db.execute(select(Chapter))).scalars().all()
        notes = (await db.execute(select(Note))).scalars().all()
        settings_rows = (await db.execute(select(Setting))).scalars().all()
        media = (await db.execute(select(MediaItem))).scalars().all()

        def _read_rel(rel: str) -> bytes | None:
            if not rel:
                return None
            p = config.DATA_DIR / rel
            try:
                return p.read_bytes()
            except OSError:
                return None

        novel_payload = []
        for n in novels:
            ch_payload = []
            for c in chapters:
                if c.novel_id != n.id:
                    continue
                content = c.content
                if not content and c.content_path:
                    raw = _read_rel(c.content_path)
                    if raw is not None:
                        text = raw.decode("utf-8", errors="replace")
                        # 磁盘文件格式为 "标题\n\n正文"，去掉首行标题
                        content = text.split("\n", 1)[1].strip() if "\n" in text else text
                ch_payload.append({"idx": c.idx, "title": c.title, "content": content})
            images_b64: dict[str, str] = {}
            img_dir = config.COVERS_DIR / n.id / "images"
            if img_dir.exists():
                for f in sorted(img_dir.iterdir()):
                    if f.is_file():
                        images_b64[f.name] = base64.b64encode(f.read_bytes()).decode()
            cover_b64 = ""
            cover_raw = _read_rel(n.cover_path)
            if cover_raw:
                cover_b64 = base64.b64encode(cover_raw).decode()
            novel_payload.append({
                "backup_id": n.id,  # 备份内稳定引用，导入时用于笔记映射
                "title": n.title, "author": n.author,
                "source_url": n.source_url, "description": n.description,
                "file_type": n.file_type, "category": n.category,
                "total_chapters": n.total_chapters, "read_chapters": n.read_chapters,
                "last_chapter_idx": n.last_chapter_idx, "last_scroll_pos": n.last_scroll_pos,
                "chapters": ch_payload,
                "cover_jpeg_b64": cover_b64,
                "images_b64": images_b64,
            })
        payload = {
            "app": "MoRead", "version": 3,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "novels": novel_payload,
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
    # 原子写：先写临时文件再替换，避免中途失败留下损坏备份；同步 I/O 移出事件循环
    import asyncio
    import os

    def _write_atomic() -> None:
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, out)

    await asyncio.to_thread(_write_atomic)
    return FileResponse(out, media_type="application/json", filename=out.name)


@router.post("/backup/import")
async def backup_import(request_bytes: dict) -> dict:
    """Accept decrypted backup JSON. v3（含笔记映射）/ v2 / v1 均可。"""
    import asyncio
    import base64
    import os
    import uuid as _uuid

    if request_bytes.get("app") != "MoRead":
        raise HTTPException(400, "不是有效的墨读备份文件")
    restored_novels = restored_notes = skipped_notes = 0
    id_map: dict[str, str] = {}  # 备份内 novel_id -> 本库 novel_id
    novel_writes: list[tuple] = []  # (dir, filename, text) 大书章节落盘任务

    def _write_batch(jobs: list[tuple]) -> None:
        for d, name, text in jobs:
            d.mkdir(parents=True, exist_ok=True)
            (d / name).write_text(text, encoding="utf-8")

    async with SessionLocal() as db:
        for n in request_bytes.get("novels", []):
            backup_id = n.get("backup_id", "")
            exists = await db.scalar(select(Novel).where(Novel.title == n.get("title", ""), Novel.author == n.get("author", "")))
            if exists:
                # 已存在：不重建，但记录映射，使笔记挂到现有书籍
                if backup_id:
                    id_map[backup_id] = exists.id
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
            if backup_id:
                id_map[backup_id] = novel.id
            chapter_payload = n.get("chapters", [])
            # 与导入逻辑一致：小书正文内联，大书落盘为章节文件
            total_text = sum(len(c.get("content", "")) for c in chapter_payload)
            inline = total_text <= 2 * 1024 * 1024 and n.get("file_type", "txt") == "txt"
            novel_dir = config.NOVELS_DIR / novel.id
            for i, c in enumerate(chapter_payload):
                content = c.get("content", "")
                if inline:
                    cpath, ccontent = "", content
                else:
                    cfile = novel_dir / f"{i:05d}.txt"
                    # 同步写盘收拢后移出事件循环执行
                    novel_writes.append((novel_dir, f"{i:05d}.txt", f"{c.get('title', '')}\n\n{content}"))
                    cpath, ccontent = cfile.relative_to(config.DATA_DIR).as_posix(), ""
                db.add(Chapter(novel_id=novel.id, idx=c.get("idx", i),
                               title=c.get("title", ""), content_path=cpath,
                               content=ccontent, word_count=len(content)))
            novel.total_chapters = len(chapter_payload)
            # v2+: 封面与 EPUB 图片
            if n.get("cover_jpeg_b64"):
                try:
                    cover_dir = config.COVERS_DIR / novel.id
                    cover_dir.mkdir(parents=True, exist_ok=True)
                    (cover_dir / "cover.jpg").write_bytes(base64.b64decode(n["cover_jpeg_b64"]))
                    novel.cover_path = (cover_dir / "cover.jpg").relative_to(config.DATA_DIR).as_posix()
                except Exception:
                    pass
            if n.get("images_b64"):
                img_dir = config.COVERS_DIR / novel.id / "images"
                img_dir.mkdir(parents=True, exist_ok=True)
                for name, b64 in n["images_b64"].items():
                    safe = _uuid.uuid4().hex[:8] + "-" + "".join(ch for ch in name if ch.isalnum() or ch in "._-")[:60]
                    try:
                        (img_dir / safe).write_bytes(base64.b64decode(b64))
                    except Exception:
                        continue
            restored_novels += 1
        if novel_writes:
            await asyncio.to_thread(_write_batch, novel_writes)
        for t in request_bytes.get("notes", []):
            # 通过 backup_id 映射到新库 ID；映射不到（v1 备份/书籍缺失）则跳过
            mapped = id_map.get(t.get("novel_id", ""))
            if not mapped:
                skipped_notes += 1
                continue
            # 重复导入去重：同书同章同内容视为同一条笔记
            dup = await db.scalar(
                select(Note.id).where(
                    Note.novel_id == mapped,
                    Note.chapter_idx == t.get("chapter_idx", 0),
                    Note.content == t.get("content", ""),
                )
            )
            if dup:
                continue
            db.add(Note(novel_id=mapped, chapter_id=None,
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
    msg = f"已恢复 {restored_novels} 本小说与 {restored_notes} 条笔记"
    if skipped_notes:
        msg += f"（{skipped_notes} 条笔记因原书缺失未恢复）"
    return {"restored_novels": restored_novels, "restored_notes": restored_notes,
            "skipped_notes": skipped_notes, "message": msg}


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
