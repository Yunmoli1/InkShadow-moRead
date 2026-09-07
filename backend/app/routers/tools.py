"""Tool endpoints: list, search, download."""

import asyncio

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..database import SessionLocal
from ..models import DownloadTask
from ..schemas import (
    DownloadCreated, DownloadRequest, SearchResult, SearchRequest, ToolOut,
)
from ..services import tool_registry
from ..services.task_manager import manager

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("", response_model=list[ToolOut])
async def list_tools() -> list[ToolOut]:
    out: list[ToolOut] = []
    for spec in tool_registry.REGISTRY.values():
        ver = await tool_registry.detect_version(spec)
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
    if low.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")):
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
        "page": "page", "novel": "novel",
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
