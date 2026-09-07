"""Builtin single-page snapshot saver (fallback when no archive tool is installed).

This is NOT a crawler: it fetches exactly one URL and saves the HTML document.
External tools (ArchiveBox etc.) are always preferred; this exists so the app
remains functional out of the box.
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urlparse

import httpx


async def save_single_page(url: str, out_dir: str) -> AsyncIterator[dict]:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    yield {"progress": 5, "message": "连接目标网页…", "log": f"GET {url}"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=30, headers={
        "User-Agent": "Mozilla/5.0 (compatible; MoRead/1.0; personal local knowledge base)",
    }) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        yield {"progress": 50, "message": "已下载 HTML，正在保存…", "log": f"{resp.status_code} {len(resp.content)} bytes"}
        await asyncio.sleep(0.05)
        ctype = resp.headers.get("content-type", "")
        parsed = urlparse(url)
        safe_host = re.sub(r"[^\w.-]", "_", parsed.netloc) or "page"
        if "html" in ctype or not ctype:
            html = resp.text
            m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
            name = re.sub(r'[\\/:*?"<>|]', "_", m.group(1).strip())[:60] if m else safe_host
            f = Path(out_dir) / f"{name or safe_host}.html"
            f.write_text(html, encoding="utf-8", errors="replace")
        else:
            f = Path(out_dir) / (safe_host + "_download")
            f.write_bytes(resp.content)
    yield {"progress": 95, "message": f"已保存 {f.name}", "log": f"saved: {f.name}"}
