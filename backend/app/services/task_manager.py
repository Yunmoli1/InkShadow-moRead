"""Task manager: subprocess lifecycle, SSE event bus, pause/resume/cancel.

Every download task runs an external tool via asyncio.create_subprocess_exec.
stdout/stderr are streamed line-by-line: parsed into progress events that are
fanned out to SSE subscribers, and kept in a log tail persisted to DB.
"""
from __future__ import annotations

import asyncio
import re
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from .. import config
from ..database import SessionLocal
from ..models import DownloadTask, MediaItem, Novel
from . import tool_registry
from .novel_parser import import_novel_file
from .web_saver import save_single_page

MAX_LOG_LINES = 200
MAX_CONCURRENT_TASKS = 2
TERMINAL_STATES = {"completed", "failed", "canceled"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EventBus:
    """Fan-out event bus; one queue per SSE subscriber."""

    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = {}
        self._global: set[asyncio.Queue] = set()

    def subscribe(self, task_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subs.setdefault(task_id, set()).add(q)
        return q

    def unsubscribe(self, task_id: str, q: asyncio.Queue) -> None:
        self._subs.get(task_id, set()).discard(q)

    def subscribe_global(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._global.add(q)
        return q

    def unsubscribe_global(self, q: asyncio.Queue) -> None:
        self._global.discard(q)

    async def publish(self, task_id: str, event: dict) -> None:
        for q in list(self._subs.get(task_id, set())) + list(self._global):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def has_subscribers(self, task_id: str) -> bool:
        return bool(self._subs.get(task_id))


bus = EventBus()


class TaskManager:
    def __init__(self) -> None:
        self.processes: dict[str, asyncio.subprocess.Process] = {}
        self.pause_flags: dict[str, asyncio.Event] = {}
        self.cancel_flags: dict[str, asyncio.Event] = {}
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
        self._worker_tasks: dict[str, asyncio.Task] = {}

    # -- create ------------------------------------------------------------

    async def create_task(
        self, tool: str, url: str, options: dict | None = None, dest_type: str = "media",
        title: str = "", task_type: str = "download",
    ) -> DownloadTask:
        spec = tool_registry.get_spec(tool)
        if spec is None:
            raise KeyError(f"未知工具: {tool}")
        options = options or {}
        out_dir = (
            config.DOWNLOADS_DIR / f"{uuid.uuid4().hex[:12]}"
        ).as_posix()
        task = DownloadTask(
            tool=tool, task_type=task_type, url=url, title=title or url,
            status="queued", output_dir=out_dir, dest_type=dest_type,
        )
        async with SessionLocal() as db:
            db.add(task)
            await db.commit()
            await db.refresh(task)
        worker = asyncio.create_task(self._run_task(task.id, spec, url, options))
        self._worker_tasks[task.id] = worker
        return task

    # -- control ------------------------------------------------------------

    async def pause(self, task_id: str) -> bool:
        self.pause_flags.setdefault(task_id, asyncio.Event()).set()
        proc = self.processes.get(task_id)
        if proc and proc.returncode is None:
            await self._terminate(proc)
        await self._update_status(task_id, status="paused", message="已暂停（进度已保留，可断点续传）")
        return True

    async def resume(self, task_id: str) -> bool:
        async with SessionLocal() as db:
            task = await db.get(DownloadTask, task_id)
            if task is None:
                return False
            if task.status != "paused":
                return False
            spec = tool_registry.get_spec(task.tool)
            url = task.url
            options = {}
        self.pause_flags.pop(task_id, None)
        await self._update_status(task_id, status="queued", message="已恢复排队")
        worker = asyncio.create_task(self._run_task(task_id, spec, url, options))
        self._worker_tasks[task_id] = worker
        return True

    async def cancel(self, task_id: str) -> bool:
        self.cancel_flags.setdefault(task_id, asyncio.Event()).set()
        proc = self.processes.get(task_id)
        if proc and proc.returncode is None:
            await self._terminate(proc)
        worker = self._worker_tasks.pop(task_id, None)
        if worker and not worker.done():
            worker.cancel()
        await self._update_status(task_id, status="canceled", message="已取消")
        await bus.publish(task_id, {"task_id": task_id, "status": "canceled", "progress": None})
        return True

    async def wait_done(self, task_id: str, timeout: float = 10.0) -> None:
        worker = self._worker_tasks.get(task_id)
        if worker:
            try:
                await asyncio.wait_for(asyncio.shield(worker), timeout=timeout)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                pass

    # -- runner ------------------------------------------------------------

    async def _run_task(self, task_id: str, spec: tool_registry.ToolSpec, url: str, options: dict) -> None:
        async with self._semaphore:
            try:
                await self._execute(task_id, spec, url, options)
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # never crash the app on tool failure
                await self._update_status(task_id, status="failed", message=f"任务执行异常: {exc}")
                await bus.publish(task_id, {"task_id": task_id, "status": "failed", "error": str(exc)})

    async def _execute(self, task_id: str, spec: tool_registry.ToolSpec, url: str, options: dict) -> None:
        log_tail: deque[str] = deque(maxlen=MAX_LOG_LINES)

        async with SessionLocal() as db:
            task = await db.get(DownloadTask, task_id)
            if task is None or task.status in TERMINAL_STATES:
                return
            task.status = "running"
            task.started_at = _now()
            task.message = "启动工具…"
            task.log_tail = []
            out_dir = task.output_dir
            argv_snapshot: list[str] = []
            await db.commit()

        if spec.name == "builtin-web-saver":
            await self._run_builtin_saver(task_id, url, out_dir, log_tail)
            return

        exe = tool_registry.resolve_executable(spec)
        if exe is None:
            await self._update_status(
                task_id, status="failed",
                message=f"工具 {spec.display} 未安装。请先安装：{spec.install_hint}",
            )
            await bus.publish(task_id, {"task_id": task_id, "status": "failed", "error": "tool-not-installed"})
            return

        config.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        argv = tool_registry.build_download_argv(spec, exe, url, out_dir, options)
        async with SessionLocal() as db:
            task = await db.get(DownloadTask, task_id)
            task.argv = argv  # type: ignore[assignment]
            await db.commit()

        try:
            # lncrawl 4.x writes output relative to CWD; archivebox needs its data dir
            cwd = out_dir if spec.name in ("lncrawl", "archivebox") else None
            Path(cwd).mkdir(parents=True, exist_ok=True) if cwd else None
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                stdin=asyncio.subprocess.DEVNULL,
                creationflags=tool_registry._NO_WINDOW,
                cwd=cwd,
            )
        except Exception as exc:
            await self._update_status(task_id, status="failed", message=f"无法启动工具进程: {exc}")
            await bus.publish(task_id, {"task_id": task_id, "status": "failed", "error": str(exc)})
            return

        self.processes[task_id] = proc
        progress = 0.0
        speed = eta = ""
        files_seen = 0
        buf = ""

        def split_lines(chunk: str) -> list[str]:
            # tools like tqdm emit \r-separated progress updates
            nonlocal buf
            buf += chunk
            parts = re.split(r"[\r\n]+", buf)
            buf = parts.pop()  # keep partial tail
            return [p for p in parts if p.strip()]

        assert proc.stdout is not None
        while True:
            if task_id in self.cancel_flags:
                break
            raw = await proc.stdout.read(1024)
            if not raw:
                break
            lines = split_lines(raw.decode("utf-8", errors="replace"))
            for line in lines:
                line = line.strip()
                log_tail.append(line)
                info = tool_registry.parse_progress_line(spec, line)
                if "progress" in info:
                    progress = max(progress, float(info["progress"]))
                speed = info.get("speed", speed)
                eta = info.get("eta", eta)
                message = info.get("message", "")
                if info.get("progress") or message:
                    await self._update_status(
                        task_id, progress=progress, speed=speed, eta=eta,
                        message=message or f"运行中 {progress:.1f}%",
                        log_lines=list(log_tail)[-MAX_LOG_LINES:],
                    )
                    await bus.publish(task_id, {
                        "task_id": task_id, "status": "running",
                        "progress": round(progress, 2), "speed": speed, "eta": eta,
                        "message": message,
                    })

        rc = await proc.wait()
        self.processes.pop(task_id, None)

        canceled = task_id in self.cancel_flags
        paused = self.pause_flags.get(task_id) is not None and not canceled

        async with SessionLocal() as db:
            task = await db.get(DownloadTask, task_id)
            task.log_tail = list(log_tail)[-MAX_LOG_LINES:]  # type: ignore[assignment]
            await db.commit()

        if canceled:
            await self._update_status(task_id, status="canceled", message="已取消")
            await bus.publish(task_id, {"task_id": task_id, "status": "canceled"})
        elif paused:
            await self._update_status(
                task_id, status="paused", progress=progress,
                message=f"已暂停于 {progress:.0f}%（断点续传可用）",
            )
            await bus.publish(task_id, {"task_id": task_id, "status": "paused", "progress": progress})
        elif rc == 0:
            imported = await self._post_process(task_id, spec, url, out_dir)
            await self._update_status(
                task_id, status="completed", progress=100.0,
                message=f"下载完成，已导入 {imported} 项资源",
            )
            await bus.publish(task_id, {"task_id": task_id, "status": "completed", "progress": 100.0, "imported": imported})
        else:
            tail = "\n".join(list(log_tail)[-5:])
            await self._update_status(
                task_id, status="failed", message=f"工具退出码 {rc}。最近日志：{tail[-400:]}",
            )
            await bus.publish(task_id, {"task_id": task_id, "status": "failed", "error": f"exit code {rc}"})

        self.cancel_flags.pop(task_id, None)
        self.pause_flags.pop(task_id, None)
        self._worker_tasks.pop(task_id, None)

    # -- builtin single page saver -------------------------------------------

    async def _run_builtin_saver(self, task_id: str, url: str, out_dir: str, log_tail: deque) -> None:
        try:
            async for event in save_single_page(url, out_dir):
                if task_id in self.cancel_flags:
                    break
                if event.get("log"):
                    log_tail.append(event["log"])
                await self._update_status(
                    task_id, progress=event.get("progress"), message=event.get("message", ""),
                    log_lines=list(log_tail)[-MAX_LOG_LINES:],
                )
                await bus.publish(task_id, {"task_id": task_id, "status": "running", **{
                    k: v for k, v in event.items() if k in ("progress", "message")
                }})
            if task_id in self.cancel_flags:
                await self._update_status(task_id, status="canceled", message="已取消")
                await bus.publish(task_id, {"task_id": task_id, "status": "canceled"})
            else:
                imported = await self._post_process(task_id, tool_registry.get_spec("builtin-web-saver"), url, out_dir)
                await self._update_status(task_id, status="completed", progress=100.0,
                                          message=f"归档完成，导入 {imported} 项")
                await bus.publish(task_id, {"task_id": task_id, "status": "completed", "progress": 100.0})
        except Exception as exc:
            await self._update_status(task_id, status="failed", message=f"网页保存失败: {exc}")
            await bus.publish(task_id, {"task_id": task_id, "status": "failed", "error": str(exc)})
        finally:
            self.cancel_flags.pop(task_id, None)
            self._worker_tasks.pop(task_id, None)

    # -- post download import -------------------------------------------------

    @staticmethod
    def _lncrawl_data_dirs() -> list[Path]:
        import os
        home = Path.home()
        dirs: list[Path] = []
        appdata = os.environ.get("APPDATA")
        if appdata:
            dirs.append(Path(appdata) / "LNCrawl" / "novels")
        dirs += [
            home / ".local" / "share" / "LNCrawl" / "novels",
            home / ".config" / "LNCrawl" / "novels",
            home / "Library" / "Application Support" / "LNCrawl" / "novels",
        ]
        return [d for d in dirs if d.exists()]

    async def _harvest_lncrawl_artifacts(self, task_id: str, out_dir: str, started_at: datetime | None) -> int:
        """lncrawl 4.x writes artifacts to its own app-data dir; copy new ones back."""
        import zipfile as zf
        since = started_at.timestamp() if started_at else 0
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        copied = 0
        for base in self._lncrawl_data_dirs():
            for artifacts in base.glob("*/artifacts"):
                for f in artifacts.iterdir():
                    if not f.is_file() or f.stat().st_mtime < since:
                        continue
                    if f.suffix == ".zip":
                        try:
                            with zf.ZipFile(f) as z:
                                for name in z.namelist():
                                    if name.endswith((".txt", ".epub", ".jpg", ".png", ".jpeg")):
                                        target = out / Path(name).name
                                        target.write_bytes(z.read(name))
                                        copied += 1
                        except zf.BadZipFile:
                            continue
                    elif f.suffix in (".txt", ".epub"):
                        target = out / f.name
                        if not target.exists():
                            target.write_bytes(f.read_bytes())
                            copied += 1
        return copied

    async def _post_process(self, task_id: str, spec: tool_registry.ToolSpec, url: str, out_dir: str) -> int:
        """Scan the output dir and import files into media/novel libraries."""
        imported = 0
        root = (
            Path(out_dir) if out_dir.startswith(config.DATA_DIR.as_posix())
            else config.DATA_DIR / out_dir.lstrip("./")
        )
        base = root if root.exists() else config.DOWNLOADS_DIR / task_id
        if not base.exists():
            return 0
        if spec.category == "novel":
            if spec.name == "lncrawl":
                async with SessionLocal() as db:
                    task = await db.get(DownloadTask, task_id)
                    started = task.started_at if task else None
                await self._harvest_lncrawl_artifacts(task_id, out_dir, started)
                from .novel_parser import import_lncrawl_output
                novel = await import_lncrawl_output(base, source_url=url)
                if novel is not None:
                    return 1
            for f in sorted(base.rglob("*")):
                if f.is_file() and f.suffix.lower() in (".txt", ".epub"):
                    if f.stat().st_size < 200:  # skip empty artifacts
                        continue
                    try:
                        await import_novel_file(f, source_url=url)
                        imported += 1
                    except Exception:
                        pass
            return imported
        # media: classify files
        kind_map = {
            ".jpg": "image", ".jpeg": "image", ".png": "image", ".gif": "image", ".webp": "image",
            ".bmp": "image", ".avif": "image", ".svg": "image",
            ".mp4": "video", ".mkv": "video", ".webm": "video", ".mov": "video", ".avi": "video", ".flv": "video",
            ".mp3": "audio", ".m4a": "audio", ".flac": "audio", ".wav": "audio", ".ogg": "audio", ".opus": "audio",
            ".html": "page", ".pdf": "doc",
        }
        async with SessionLocal() as db:
            for f in sorted(base.rglob("*")):
                if not f.is_file():
                    continue
                if f.name.startswith(".") or f.suffix.lower() in (".part", ".ytdl", ".tmp", ".json", ".txt", ".log"):
                    continue
                mtype = kind_map.get(f.suffix.lower())
                if not mtype:
                    continue
                size = f.stat().st_size
                if size == 0:
                    continue
                rel = f.relative_to(config.DATA_DIR).as_posix()
                exists = await db.scalar(
                    select(MediaItem.id).where(MediaItem.file_path == rel, MediaItem.source_url == url)
                )
                if exists:
                    continue
                db.add(MediaItem(
                    media_type=mtype, title=f.stem, source_url=url,
                    file_path=rel, mime_type=_guess_mime(f), file_size=size,
                    extra={"task_id": task_id, "dir": base.name},
                ))
                imported += 1
            await db.commit()
        return imported

    # -- helpers ------------------------------------------------------------

    async def _update_status(self, task_id: str, **fields) -> None:
        async with SessionLocal() as db:
            task = await db.get(DownloadTask, task_id)
            if task is None:
                return
            for k, v in fields.items():
                if v is not None:
                    setattr(task, k, v)
            if "log_lines" in fields:
                task.log_tail = fields["log_lines"]  # type: ignore[assignment]
                fields.pop("log_lines", None)
            if fields.get("status") in TERMINAL_STATES:
                task.finished_at = _now()
            await db.commit()

    @staticmethod
    async def _terminate(proc: asyncio.subprocess.Process) -> None:
        try:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()
        except ProcessLookupError:
            pass


def _guess_mime(f) -> str:
    import mimetypes
    return mimetypes.guess_type(f.name)[0] or "application/octet-stream"


manager = TaskManager()
