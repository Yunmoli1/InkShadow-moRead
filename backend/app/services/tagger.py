"""AI 自动标签（Karakeep 模式）：本地 Ollama / OpenAI 兼容接口生成 3-5 个短标签。

任何失败都返回空列表（静默跳过），绝不影响导入流程。
"""
from __future__ import annotations

import json
import re

import httpx
from sqlalchemy import select


def _parse_tags(text: str) -> list[str]:
    """从模型输出解析标签数组；容错：截取 [ ... ] 片段。"""
    m = re.search(r"\[.*?\]", text, re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
        if isinstance(arr, list):
            out = []
            for t in arr:
                t = str(t).strip().strip("#")
                if 1 <= len(t) <= 16 and t not in out:
                    out.append(t)
            return out[:5]
    except (ValueError, TypeError):
        pass
    return []


async def auto_tag(title: str, snippet: str, settings: dict) -> list[str]:
    base_url = (settings.get("ai_base_url") or "http://localhost:11434").rstrip("/")
    api_key = settings.get("ai_api_key") or ""
    model = settings.get("ai_model") or "llama3"
    style = settings.get("ai_style") or "ollama"
    proxy = (settings.get("proxy_url") or "").strip()
    from .ai_service import should_proxy

    client_kwargs = {"proxy": proxy} if should_proxy(base_url, proxy) else {}
    prompt = (
        "为以下内容生成3到5个简短中文标签（每个不超过8个字），"
        '只输出JSON数组，例如 ["奇幻","冒险","等级体系"]。不要输出其他文字。\n\n'
        f"标题：{title}\n内容摘要：{snippet[:1500]}"
    )
    try:
        if style == "openai":
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            async with httpx.AsyncClient(timeout=60, headers=headers, **client_kwargs) as client:
                resp = await client.post(
                    f"{base_url}/v1/chat/completions",
                    json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2},
                )
                resp.raise_for_status()
                return _parse_tags(resp.json()["choices"][0]["message"]["content"])
        async with httpx.AsyncClient(timeout=60, **client_kwargs) as client:
            resp = await client.post(
                f"{base_url}/api/chat",
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False},
            )
            resp.raise_for_status()
            return _parse_tags((resp.json().get("message") or {}).get("content") or "")
    except Exception:
        return []


async def tag_novel(novel_id: str) -> list[str]:
    """为小说生成标签并写库（后台调用）。"""
    from ..database import SessionLocal
    from ..models import Novel, Setting

    async with SessionLocal() as db:
        n = await db.get(Novel, novel_id)
        if n is None or n.tags:
            return []
        title, text = n.title, (n.description or "")
        if not text:
            from sqlalchemy import select

            from ..models import Chapter

            rows = (await db.execute(
                select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.idx).limit(1)
            )).scalars().all()
            if rows:
                content = rows[0].content
                if not content and rows[0].content_path:
                    p = config.DATA_DIR / rows[0].content_path
                    if p.exists():
                        try:
                            content = p.read_text(encoding="utf-8", errors="replace")
                        except OSError:
                            content = ""
                text = content
        settings_rows = (await db.execute(select(Setting))).scalars().all()
        settings = {s.key: s.value for s in settings_rows}
    tags = await auto_tag(title, text or title, settings)
    if tags:
        async with SessionLocal() as db:
            n = await db.get(Novel, novel_id)
            if n is not None and not n.tags:
                n.tags = tags
                await db.commit()
    return tags


async def tag_media(media_id: str) -> list[str]:
    """为媒体项生成标签并写库（后台调用）。"""
    from ..database import SessionLocal
    from ..models import MediaItem, Setting

    async with SessionLocal() as db:
        m = await db.get(MediaItem, media_id)
        if m is None or m.extra.get("tags"):
            return []
        title = m.title
        snippet = m.source_url or m.mime_type or ""
        settings_rows = (await db.execute(select(Setting))).scalars().all()
        settings = {s.key: s.value for s in settings_rows}
    tags = await auto_tag(title, f"{snippet} {title}", settings)
    if tags:
        async with SessionLocal() as db:
            m = await db.get(MediaItem, media_id)
            if m is not None:
                extra = dict(m.extra or {})
                extra["tags"] = tags
                m.extra = extra
                await db.commit()
    return tags
