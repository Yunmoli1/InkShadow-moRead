"""OPDS 目录（第四步）：让 KOReader / Moon+ Reader 等阅读 App 订阅墨读书库。

- GET /opds          根导航 feed
- GET /opds/books    书目 acquisition feed（含 TXT 下载链接）
- GET /api/novels/{id}/download.txt   整本书 TXT 流式下载

鉴权：与 API 相同的访问令牌——支持 ?token=、X-MoRead-Token，
以及 OPDS 客户端普遍使用的 HTTP Basic（用户名任意，密码=令牌）。
"""
from __future__ import annotations

import hmac
from xml.sax.saxutils import escape

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select

from .. import config
from ..database import SessionLocal
from ..models import Chapter, Novel
from ..services.token_guard import current_token

router = APIRouter(tags=["opds"])

NAV_TYPE = "application/atom+xml;profile=opds-catalog;kind=navigation"
ACQ_TYPE = "application/atom+xml;profile=opds-catalog;kind=acquisition"


async def _authorized(request: Request) -> bool:
    token = await current_token()
    if not token:
        return True
    provided = request.query_params.get("token") or ""
    if not provided:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("basic "):
            import base64

            try:
                decoded = base64.b64decode(auth[6:]).decode("utf-8", errors="replace")
                provided = decoded.split(":", 1)[1]  # 用户名任意，密码=令牌
            except Exception:
                provided = ""
        else:
            provided = request.headers.get("x-moread-token") or ""
    return hmac.compare_digest(provided, token)


def _feed(feed_id: str, title: str, self_href: str, entries: list[dict]) -> str:
    from datetime import datetime, timezone

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog">',
        f"<id>{escape(feed_id)}</id>",
        f"<title>{escape(title)}</title>",
        f"<updated>{updated}</updated>",
        f'<link rel="self" href="{escape(self_href)}" type="{ACQ_TYPE}"/>',
    ]
    for e in entries:
        parts.append("<entry>")
        parts.append(f"<id>{escape(e['id'])}</id>")
        parts.append(f"<title>{escape(e['title'])}</title>")
        parts.append(f"<updated>{updated}</updated>")
        if e.get("author"):
            parts.append(f"<author><name>{escape(e['author'])}</name></author>")
        if e.get("summary"):
            parts.append(f"<summary type=\"text\">{escape(e['summary'])}</summary>")
        for link in e.get("links", []):
            parts.append(
                f'<link rel="{escape(link["rel"])}" href="{escape(link["href"])}" '
                f'type="{escape(link["type"])}"/>'
            )
        parts.append("</entry>")
    parts.append("</feed>")
    return "\n".join(parts)


@router.get("/opds")
async def opds_root(request: Request):
    if not await _authorized(request):
        return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="MoRead"'})
    xml = _feed("moread-root", "墨读 MoRead 书库", "/opds", [
        {
            "id": "moread-all-books",
            "title": "全部书籍",
            "summary": "书架上的全部小说与文章（TXT 下载）",
            "links": [{"rel": "subsection", "type": ACQ_TYPE, "href": "/opds/books"}],
        },
    ])
    return Response(content=xml, media_type=NAV_TYPE)


@router.get("/opds/books")
async def opds_books(request: Request):
    if not await _authorized(request):
        return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="MoRead"'})
    token = request.query_params.get("token") or ""
    suffix = f"?token={token}" if token else ""
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(Novel).order_by(Novel.updated_at.desc()).limit(500)
        )).scalars().all()
    entries = []
    for n in rows:
        entries.append({
            "id": f"moread-novel-{n.id}",
            "title": f"{n.title}（{n.total_chapters} 章）",
            "author": n.author or "佚名",
            "summary": (n.description or "")[:200] or f"分类：{n.category}",
            "links": [
                {"rel": "http://opds-spec.org/acquisition", "type": "text/plain",
                 "href": f"/api/novels/{n.id}/download.txt{suffix}"},
                # B2：EPUB 按需生成（首次访问时由后端动态打包并缓存）
                {"rel": "http://opds-spec.org/acquisition", "type": "application/epub+zip",
                 "href": f"/api/novels/{n.id}/download.epub{suffix}"},
            ],
        })
    xml = _feed("moread-books", "全部书籍", "/opds/books", entries)
    return Response(content=xml, media_type=ACQ_TYPE)


@router.get("/api/novels/{novel_id}/download.txt")
async def _download_txt(novel_id: str):
    """整本书 TXT 流式下载（OPDS acquisition 目标）。"""
    async with SessionLocal() as db:
        n = await db.get(Novel, novel_id)
        if n is None:
            return Response(status_code=404)
        chapters = (await db.execute(
            select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.idx)
        )).scalars().all()

    from urllib.parse import quote

    safe_name = "".join(ch for ch in n.title if ord(ch) < 128 and (ch.isalnum() or ch in " _-"))[:60] or "book"
    quoted = quote(n.title)  # RFC 5987：HTTP 头不支持非 ASCII 文件名

    async def gen():
        yield f"{n.title}\n作者：{n.author or '佚名'}\n\n"
        for c in chapters:
            content = c.content
            if not content and c.content_path:
                p = config.DATA_DIR / c.content_path
                if p.exists():
                    try:
                        content = p.read_text(encoding="utf-8", errors="replace")
                        content = content.split("\n", 1)[1].strip() if "\n" in content else content
                    except OSError:
                        content = ""
            yield f"\n\n{c.title}\n\n{content}\n"

    return StreamingResponse(
        gen(), media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": (
            f"attachment; filename=\"{safe_name}.txt\"; filename*=UTF-8''{quoted}.txt"
        )},
    )
