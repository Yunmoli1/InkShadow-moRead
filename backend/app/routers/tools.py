"""Tool endpoints: list, search, preview, download."""

import asyncio
import json as _json
import re

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..database import SessionLocal
from ..models import DownloadTask
from ..schemas import (
    DownloadCreated, DownloadItemsIn, DownloadRequest, PreviewRequest,
    SearchResult, SearchRequest, ToolOut,
)
from ..services import tool_registry
from ..services.task_manager import manager

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("", response_model=list[ToolOut])
async def list_tools(refresh: bool = False) -> list[ToolOut]:
    import asyncio

    specs = list(tool_registry.REGISTRY.values())
    # 并发版本检测：13 个工具从串行 ~40s 降至并行 ~15s
    versions = await asyncio.gather(
        *(tool_registry.detect_version(spec, refresh=refresh) for spec in specs)
    )
    out: list[ToolOut] = []
    for spec, ver in zip(specs, versions):
        out.append(ToolOut(
            name=spec.name,
            display=spec.display,
            category=spec.category,
            installed=ver is not None,
            version=ver,
            install_hint=spec.install_hint,
            supports_search=spec.supports_search,
            content_types=spec.content_types,
            docs_url=spec.docs_url,
            remark=spec.remark,
        ))
    return out


def _pick_tool(content_type: str, requested: str | None, url: str) -> tool_registry.ToolSpec:
    if requested:
        spec = tool_registry.get_spec(requested)
        if spec is None:
            raise HTTPException(404, f"未知工具: {requested}")
        return spec
    # auto detection by URL extension first
    low = url.lower().split("?")[0]
    # 小说站特征（.php 结尾的小说页不能按"网页归档"处理）
    if "pixiv.net/novel" in low or re.search(r"/(novel|book|xiaoshuo|read)/", low):
        content_type = content_type if content_type != "auto" else "novel"
    elif re.search(r"\.(zip|rar|7z|tar|gz|tgz|bz2|xz|apk|exe|msi|iso)$", low):
        content_type = content_type if content_type != "auto" else "file"
    elif low.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")):
        content_type = content_type if content_type != "auto" else "image"
    elif low.endswith((".mp4", ".mkv", ".webm", ".mov")):
        content_type = content_type if content_type != "auto" else "video"
    elif low.endswith((".mp3", ".m4a", ".flac", ".wav", ".ogg")):
        content_type = content_type if content_type != "auto" else "audio"
    elif low.endswith((".html", ".htm")) or low.endswith("/") or low.endswith(".php"):
        content_type = content_type if content_type != "auto" else "page"
    elif low.endswith((".txt", ".epub")):
        content_type = content_type if content_type != "auto" else "novel"

    if content_type == "auto":
        # still undecided: try universal tools, then any installed tool,
        # finally the builtin single-page saver. 万能抓取 must not hard-fail.
        for category in ("universal", "video", "image", "novel", "page"):
            spec = _first_installed(category, skip_builtin=True)
            if spec:
                return spec
        return tool_registry.get_spec("builtin-web-saver")

    category = {
        "image": "image", "video": "video", "audio": "video",
        "page": "page", "novel": "novel", "file": "file",
    }.get(content_type, "universal")

    spec = _first_installed(category, skip_builtin=True)
    if spec:
        return spec
    if content_type == "page":
        return tool_registry.get_spec("builtin-web-saver")  # final fallback
    raise HTTPException(
        400,
        f"没有可用于「{content_type}」的工具。请前往「工具箱」安装，例如：yt-dlp / gallery-dl / lncrawl。",
    )


def _first_installed(category: str, skip_builtin: bool = False) -> tool_registry.ToolSpec | None:
    for spec in tool_registry.REGISTRY.values():
        if spec.category != category:
            continue
        if skip_builtin and spec.name == "builtin-web-saver":
            continue
        if tool_registry.resolve_executable(spec) or spec.name == "builtin-web-saver":
            return spec
    return None


@router.post("/{tool_name}/search", response_model=SearchResult)
async def search_with_tool(tool_name: str, body: SearchRequest) -> SearchResult:
    spec = tool_registry.get_spec(tool_name)
    if spec is None:
        raise HTTPException(404, f"未知工具: {tool_name}")
    exe = tool_registry.resolve_executable(spec)
    if exe is None:
        raise HTTPException(400, f"工具 {spec.display} 未安装，无法搜索。安装方法：{spec.install_hint}")
    argv = tool_registry.build_search_argv(spec, exe, body.query, body.limit)
    if argv is None:
        return SearchResult(tool=tool_name, results=[], message=f"{spec.display} 不支持搜索功能")
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            creationflags=tool_registry._NO_WINDOW,
        )
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=90)
        except asyncio.TimeoutError:
            proc.kill()
            return SearchResult(tool=tool_name, results=[], message="搜索超时，请稍后重试")
    except Exception as exc:
        return SearchResult(tool=tool_name, results=[], message=f"搜索执行失败: {exc}")
    text = out.decode("utf-8", errors="replace")
    results = tool_registry.parse_search_output(spec, text)
    if not results and proc.returncode != 0:
        return SearchResult(tool=tool_name, results=[], message=f"搜索无结果（工具退出码 {proc.returncode}）")
    return SearchResult(tool=tool_name, results=results)


@router.post("/preview")
async def preview_url(body: PreviewRequest) -> dict:
    """预览下载目标：按 URL 自动选择工具，并尝试快速探测内容信息。

    probe 为 None 表示该工具不支持快速探测（或探测超时），不影响下载。"""
    spec = _pick_tool(body.content_type or "auto", body.tool, body.url)
    probe = await _probe_target(spec, body.url)
    return {
        "url": body.url,
        "tool": {
            "name": spec.name, "display": spec.display,
            "category": spec.category, "remark": spec.remark,
        },
        "probe": probe,
    }


_PROBE_TIMEOUT = 30


async def _probe_target(spec: tool_registry.ToolSpec, url: str) -> dict | None:
    exe = tool_registry.resolve_executable(spec)
    if exe is None:
        return None
    argv: list[str] | None = None
    if spec.name == "yt-dlp":
        argv = [exe, "-J", "--flat-playlist", "--no-playlist", url]
    elif spec.name == "gallery-dl":
        argv = [exe, "-g", url]
    elif spec.name == "image-harvest":
        argv = [exe, url, "--list-only", "--list-format", "json"]
    elif spec.name == "you-get":
        argv = [exe, "--json", url]
    if argv is None:
        return {"note": f"{spec.display} 不支持快速预览，可直接开始下载"}

    import os
    env = {**os.environ, "PATH": tool_registry.tool_search_path(),
           "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.DEVNULL,
            creationflags=tool_registry._NO_WINDOW,
            env=env,
        )
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=_PROBE_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            return {"note": "预览超时（目标站点响应慢或需要代理），可直接开始下载"}
    except Exception as exc:
        return {"note": f"预览失败: {exc}"}

    text = out.decode("utf-8", errors="replace").strip()
    if spec.name == "yt-dlp" and text.startswith("{"):
        try:
            data = _json.loads(text)
        except ValueError:
            return None
        if data.get("_type") == "playlist":
            entries = [e for e in (data.get("entries") or []) if e]
            items = []
            for e in entries[:20]:
                eurl = e.get("url") or e.get("webpage_url")
                if not eurl and e.get("id"):
                    eurl = f"https://www.youtube.com/watch?v={e['id']}"
                if eurl:
                    items.append({"title": e.get("title") or eurl, "url": eurl})
            return {
                "title": data.get("title") or url,
                "count": data.get("playlist_count") or len(entries),
                "items": items,
                "note": f"共 {len(entries)} 个条目，可勾选下载" if entries else "空列表",
            }
        dur = data.get("duration")
        return {
            "title": data.get("title") or url,
            "count": 1,
            "items": [{"title": f"{data.get('extractor_key', '')} · {data.get('uploader') or ''}"
                       + (f" · {int(dur // 60)}分{int(dur % 60)}秒" if dur else ""), "url": url}],
            "note": "单个媒体文件",
        }
    if spec.name == "image-harvest" and text.startswith("["):
        try:
            items = _json.loads(text)
        except ValueError:
            return None
        return {
            "title": f"发现 {len(items)} 张图片",
            "count": len(items),
            "items": [{"title": (it.get("alt") or it.get("filename") or it.get("url", "?")), "url": it.get("url", "")}
                      for it in items[:50] if it.get("url")],
            "note": f"共 {len(items)} 张图片（前 50 项可勾选下载）",
        }
    if spec.name == "gallery-dl":
        lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("http")]
        if lines:
            return {
                "title": f"发现 {len(lines)} 个媒体地址",
                "count": len(lines),
                "items": [{"title": ln.rsplit("/", 1)[-1][:60] or ln, "url": ln} for ln in lines[:50]],
                "note": f"共 {len(lines)} 项（前 50 项可勾选下载）",
            }
        return {"note": "未探测到可直接下载的内容，仍可尝试下载"}
    if spec.name == "you-get":
        try:
            data = _json.loads(text)
        except ValueError:
            return {"note": "未探测到可直接下载的内容，仍可尝试下载"}
        streams = (data.get("data") or {}).get("streams") or {}
        best = sorted(streams.values(), key=lambda s: s.get("size") or 0, reverse=True)
        if best:
            s = best[0]
            return {"title": data.get("title") or url, "count": 1,
                    "items": [{"title": f"{s.get('quality') or ''} {s.get('container') or ''}".strip() or url,
                               "url": url}],
                    "note": "单个媒体文件"}
    return None


@router.post("/items/download", response_model=DownloadCreated, status_code=201)
async def download_selected_items(body: DownloadItemsIn) -> DownloadCreated:
    """选择性下载：直接抓取用户在预览界面勾选的资源直链（图片/视频/压缩包等）。"""
    urls = [u.strip() for u in body.urls if u.strip()]
    if not urls:
        raise HTTPException(400, "未选择任何资源")
    task = await manager.create_task(
        tool="item-fetch", url=urls[0], options={"urls": urls},
        dest_type="media", title=f"选择性下载 {len(urls)} 项",
    )
    return DownloadCreated(task_id=task.id, tool="item-fetch", status=task.status,
                           message=f"已创建选择性下载任务（{len(urls)} 项）")


@router.post("/auto/download", response_model=DownloadCreated, status_code=201)
async def download_auto(body: DownloadRequest) -> DownloadCreated:
    """万能抓取：按内容类型自动挑选已安装的工具。"""
    spec = _pick_tool(body.content_type, body.tool, body.url)
    task = await manager.create_task(
        tool=spec.name, url=body.url, options=body.options,
        dest_type="novel" if spec.category == "novel" else "media",
        title=body.url,
    )
    return DownloadCreated(task_id=task.id, tool=spec.name, status=task.status,
                           message=f"已调度 {spec.display}")


@router.post("/{tool_name}/download", response_model=DownloadCreated, status_code=201)
async def download_with_tool(tool_name: str, body: DownloadRequest) -> DownloadCreated:
    spec = tool_registry.get_spec(tool_name)
    if spec is None:
        raise HTTPException(404, f"未知工具: {tool_name}")
    exe = tool_registry.resolve_executable(spec)
    if exe is None and spec.name != "builtin-web-saver":
        raise HTTPException(400, f"工具 {spec.display} 未安装。安装方法：{spec.install_hint}")
    task = await manager.create_task(
        tool=tool_name, url=body.url, options=body.options, dest_type="media",
    )
    return DownloadCreated(task_id=task.id, tool=tool_name, status=task.status,
                           message=f"任务已创建（{spec.display}）")


@router.get("/running")
async def running_tasks() -> list[dict]:
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(DownloadTask).where(DownloadTask.status.in_(["running", "queued"]))
        )).scalars().all()
        return [
            {"id": t.id, "tool": t.tool, "status": t.status, "progress": t.progress, "title": t.title}
            for t in rows
        ]
