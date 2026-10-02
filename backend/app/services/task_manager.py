"""Task manager: subprocess lifecycle, SSE event bus, pause/resume/cancel.

Every download task runs an external tool via asyncio.create_subprocess_exec.
stdout/stderr are streamed line-by-line: parsed into progress events that are
fanned out to SSE subscribers, and kept in a log tail persisted to DB.
"""
from __future__ import annotations

import asyncio
import os
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
from . import netenv
from .novel_parser import import_novel_file
from .web_saver import save_single_page

MAX_LOG_LINES = 200
MAX_CONCURRENT_TASKS = 2
TERMINAL_STATES = {"completed", "failed", "canceled"}


class NoContentError(Exception):
    """Tool exited 0 but nothing usable was produced (e.g. only an index.html
    shell). Treated as a failure so the fallback chain keeps trying."""


# settings.toml for novel-cli (Novel Downloader): all paths CWD-relative so
# downloads land inside the task's own output dir.
_NOVEL_CLI_SETTINGS = """\
[general]
raw_data_dir = "./raw_data"
output_dir = "./downloads"
cache_dir = "./novel_cache"
request_interval = 0.5
workers = 4
max_connections = 10
retry_times = 3
backoff_factor = 2.0
timeout = 30.0

[general.output]
formats = ["txt"]
append_timestamp = false
filename_template = "{title}_{author}"
include_picture = true

[general.debug]
save_html = false
log_dir = "./logs"
log_level = "INFO"
"""


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

    async def _switch_and_retry(
        self, task_id: str, spec: tool_registry.ToolSpec, url: str, options: dict,
        log_tail: deque, reason: str, _fallback: list[tool_registry.ToolSpec],
    ) -> bool:
        """Switch the task to the next installed fallback tool and re-run it.

        Returns True when a retry was started (the caller must then return
        without touching the task's terminal state again)."""
        nxt = next((s for s in _fallback if tool_registry.resolve_executable(s)), None)
        if nxt is None:
            return False
        remaining = [s for s in _fallback if s is not nxt]
        log_tail.append(f"--- {reason}，自动切换工具: {nxt.display} ---")
        await self._update_status(
            task_id, message=f"{reason}，自动切换到 {nxt.display} 重试…",
            log_lines=list(log_tail)[-MAX_LOG_LINES:],
        )
        await bus.publish(task_id, {
            "task_id": task_id, "status": "running",
            "message": f"自动切换到 {nxt.display} 重试",
        })
        async with SessionLocal() as db:
            task = await db.get(DownloadTask, task_id)
            task.tool = nxt.name
            await db.commit()
        await self._execute(task_id, nxt, url, options, _fallback=remaining)
        return True

    async def _execute(
        self, task_id: str, spec: tool_registry.ToolSpec, url: str, options: dict,
        _fallback: list[tool_registry.ToolSpec] | None = None,
    ) -> None:
        if _fallback is None:
            _fallback = tool_registry.fallback_chain(spec)
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
        if spec.name == "web2novel":
            await self._run_web2novel(task_id, url, out_dir, log_tail)
            return
        if spec.name == "item-fetch":
            await self._run_item_fetch(task_id, url, out_dir, log_tail, options)
            return

        exe = tool_registry.resolve_executable(spec)
        if exe is None:
            if await self._switch_and_retry(
                task_id, spec, url, options, log_tail,
                f"工具 {spec.display} 未安装", _fallback,
            ):
                return
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
            # lncrawl 4.x / abx-dl / archivebox / novel-cli write output relative to CWD
            cwd = out_dir if spec.name in ("lncrawl", "abx-dl", "archivebox", "novel-downloader") else None
            Path(cwd).mkdir(parents=True, exist_ok=True) if cwd else None
            env = dict(os.environ)
            env["PATH"] = tool_registry.tool_search_path()
            env.update(netenv.proxy_env(await netenv.get_proxy_url()))
            # Tools inspect their own stdout encoding (ArchiveBox refuses GBK);
            # piped output on Windows defaults to the ANSI code page otherwise.
            env.setdefault("PYTHONUTF8", "1")
            env.setdefault("PYTHONIOENCODING", "utf-8")
            if spec.name == "DXC":
                # DXC saves under <HOME>/Downloads/DXC by default; pin HOME to
                # the task dir so _post_process finds the files (rglob scan).
                env["HOME"] = env["USERPROFILE"] = out_dir
            if spec.name == "novel-downloader":
                # novel-cli requires settings.toml and is interactive when it
                # is missing (stdin is DEVNULL) — seed one that keeps every
                # artifact inside the task dir via CWD-relative paths.
                Path(cwd).mkdir(parents=True, exist_ok=True)
                (Path(cwd) / "settings.toml").write_text(_NOVEL_CLI_SETTINGS, encoding="utf-8")
            if spec.name == "archivebox":
                # Edge ships with Windows and powers the PDF/screenshot
                # extractors; without CHROME_BINARY they all fail.
                if "CHROME_BINARY" not in env:
                    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
                    if Path(edge).exists():
                        env["CHROME_BINARY"] = edge
                # `archivebox add` refuses to run outside an initialized
                # collection; the task dir is always fresh, so init it first.
                # stdin must be DEVNULL: an inherited (possibly invalid) stdin
                # handle makes the CLI exit 2 without any output.
                Path(cwd).mkdir(parents=True, exist_ok=True)
                init_rc = init_out = None
                for attempt in (1, 2):  # one retry: transient AV/file locks
                    init = await asyncio.create_subprocess_exec(
                        argv[0], "init",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.STDOUT,
                        stdin=asyncio.subprocess.DEVNULL,
                        creationflags=tool_registry._NO_WINDOW,
                        cwd=cwd, env=env,
                    )
                    init_out, _ = await init.communicate()
                    init_rc = init.returncode
                    if init_rc == 0:
                        break
                    log_tail.append(f"[init] 第 {attempt} 次尝试失败（退出码 {init_rc}），重试中…")
                    await asyncio.sleep(2)
                for line in (init_out or b"").decode("utf-8", errors="replace").splitlines()[-25:]:
                    log_tail.append(f"[init] {line.strip()}")
                if init_rc != 0:
                    raise RuntimeError(
                        f"archivebox init 失败（退出码 {init_rc}），无法创建归档集合。"
                        f"完整输出见任务日志。")
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                stdin=asyncio.subprocess.DEVNULL,
                creationflags=tool_registry._NO_WINDOW,
                cwd=cwd,
                env=env,
            )
        except Exception as exc:
            if await self._switch_and_retry(
                task_id, spec, url, options, log_tail, f"工具 {spec.display} 启动失败", _fallback,
            ):
                return
            await self._update_status(
                task_id, status="failed",
                message=f"无法启动工具进程: {exc}",
                log_lines=list(log_tail)[-MAX_LOG_LINES:],
            )
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
        STALL_TIMEOUT = 300  # a tool printing nothing for 5 min is considered hung
        while True:
            if task_id in self.cancel_flags:
                break
            try:
                raw = await asyncio.wait_for(proc.stdout.read(1024), timeout=STALL_TIMEOUT)
            except asyncio.TimeoutError:
                log_tail.append(f"[watchdog] 工具已 {STALL_TIMEOUT}s 无任何输出，判定卡死并终止")
                await self._terminate(proc)
                rc = await proc.wait()
                self.processes.pop(task_id, None)
                canceled = task_id in self.cancel_flags
                paused = False
                await self._finish(task_id, spec, url, options, out_dir, log_tail, rc, canceled, False, _fallback,
                                   note="工具卡死无输出，已被自动终止", progress=progress)
                return
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
        await self._finish(task_id, spec, url, options, out_dir, log_tail, rc, canceled, paused, _fallback, progress=progress)

    async def _finish(
        self, task_id: str, spec: tool_registry.ToolSpec, url: str, options: dict,
        out_dir: str, log_tail: deque, rc: int, canceled: bool, paused: bool,
        _fallback: list[tool_registry.ToolSpec] | None, note: str = "", progress: float = 0.0,
    ) -> None:
        prefix = f"{note}；" if note else ""
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
            try:
                imported = await self._post_process(task_id, spec, url, out_dir)
            except NoContentError as exc:
                if await self._switch_and_retry(
                    task_id, spec, url, options, log_tail, str(exc), _fallback or [],
                ):
                    return
                await self._update_status(
                    task_id, status="failed", message=f"{prefix}{exc}",
                    log_lines=list(log_tail)[-MAX_LOG_LINES:],
                )
                await bus.publish(task_id, {"task_id": task_id, "status": "failed", "error": "no-content"})
                return
            await self._update_status(
                task_id, status="completed", progress=100.0,
                message=f"下载完成，已导入 {imported} 项资源",
            )
            await bus.publish(task_id, {"task_id": task_id, "status": "completed", "progress": 100.0, "imported": imported})
        else:
            tail = "\n".join(list(log_tail)[-5:])
            if await self._switch_and_retry(
                task_id, spec, url, options, log_tail,
                f"工具 {spec.display} 失败（退出码 {rc}）", _fallback or [],
            ):
                return
            await self._update_status(
                task_id, status="failed", message=f"{prefix}工具退出码 {rc}。最近日志：{tail[-400:]}",
            )
            await bus.publish(task_id, {"task_id": task_id, "status": "failed", "error": f"exit code {rc}"})

        self.cancel_flags.pop(task_id, None)
        self.pause_flags.pop(task_id, None)
        self._worker_tasks.pop(task_id, None)

    # -- builtin direct-file fetcher (selective / archive downloads) ----------

    async def _run_item_fetch(self, task_id: str, url: str, out_dir: str,
                              log_tail: deque, options: dict) -> None:
        import re as _re
        from urllib.parse import unquote

        import httpx

        from .netenv import get_proxy_url, should_proxy

        urls = [u for u in (options.get("urls") or [url]) if u]
        total = max(1, len(urls))
        proxy = await get_proxy_url()
        ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        done = ok = 0

        async def fetch_one(client: httpx.AsyncClient, u: str) -> None:
            nonlocal ok
            resp = await client.get(u)
            resp.raise_for_status()
            name = None
            cd = resp.headers.get("content-disposition", "")
            m = _re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
            if m:
                name = unquote(m.group(1).strip())
            if not name:
                path = u.split("://", 1)[-1].split("?", 1)[0].rstrip("/")
                name = unquote(path.rsplit("/", 1)[-1]) or "file"
            name = _re.sub(r'[\\/:*?"<>|]+', "_", name)[:120] or "file"
            (Path(out_dir) / name).write_bytes(resp.content)
            ok += 1
            log_tail.append(f"saved: {name} ({len(resp.content)} bytes)")

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=120,
                                         headers={"User-Agent": ua},
                                         proxy=proxy if should_proxy(url, proxy) else None) as client:
                for i, u in enumerate(urls):
                    if task_id in self.cancel_flags:
                        break
                    try:
                        await fetch_one(client, u)
                    except Exception as exc:
                        log_tail.append(f"FAILED: {u} ({exc})")
                    await self._update_status(
                        task_id, progress=round((i + 1) / total * 90, 1),
                        message=f"已下载 {ok}/{i + 1} 个文件",
                        log_lines=list(log_tail)[-MAX_LOG_LINES:],
                    )
                    await bus.publish(task_id, {"task_id": task_id, "status": "running",
                                                "message": f"已下载 {ok}/{i + 1} 个文件"})
            if task_id in self.cancel_flags:
                await self._update_status(task_id, status="canceled", message="已取消")
                await bus.publish(task_id, {"task_id": task_id, "status": "canceled"})
                return
            if ok == 0:
                raise RuntimeError("所有文件均下载失败")
            imported = await self._post_process(task_id, tool_registry.get_spec("item-fetch"), url, out_dir)
            await self._update_status(task_id, status="completed", progress=100.0,
                                      message=f"下载完成（{ok}/{total}），已导入 {imported} 项")
            await bus.publish(task_id, {"task_id": task_id, "status": "completed",
                                        "progress": 100.0, "imported": imported})
        except Exception as exc:
            await self._update_status(task_id, status="failed", message=f"文件下载失败: {exc}",
                                      log_lines=list(log_tail)[-MAX_LOG_LINES:])
            await bus.publish(task_id, {"task_id": task_id, "status": "failed", "error": str(exc)})
        finally:
            self.cancel_flags.pop(task_id, None)
            self._worker_tasks.pop(task_id, None)

    # -- builtin webpage→novel converter --------------------------------------

    async def _run_web2novel(self, task_id: str, url: str, out_dir: str, log_tail: deque) -> None:
        from .web2novel import save_web_novel
        try:
            async for event in save_web_novel(url, out_dir):
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
                spec = tool_registry.get_spec("web2novel")
                imported = await self._post_process(task_id, spec, url, out_dir)
                await self._update_status(task_id, status="completed", progress=100.0,
                                          message=f"已转为小说，导入 {imported} 项")
                await bus.publish(task_id, {"task_id": task_id, "status": "completed", "progress": 100.0})
        except Exception as exc:
            if await self._switch_and_retry(
                task_id, tool_registry.get_spec("web2novel"), url, {}, log_tail,
                f"网页转小说失败: {exc}", [],
            ):
                return
            await self._update_status(task_id, status="failed", message=f"网页转小说失败: {exc}")
            await bus.publish(task_id, {"task_id": task_id, "status": "failed", "error": str(exc)})
        finally:
            self.cancel_flags.pop(task_id, None)
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

    async def _harvest_sonovel_artifacts(self, task_id: str, out_dir: str) -> int:
        """so-novel has no output-path option: it writes into its own app dir
        (tools/bin/so-novel/SoNovel/downloads). Copy files produced during
        this task back into the task dir for import."""
        async with SessionLocal() as db:
            task = await db.get(DownloadTask, task_id)
            since = (task.started_at.timestamp() - 60) if task and task.started_at else 0
        src = config.TOOLS_DIR / "bin" / "so-novel" / "SoNovel" / "downloads"
        if not src.is_dir():
            return 0
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        copied = 0
        for f in src.rglob("*"):
            if f.is_file() and f.stat().st_mtime >= since:
                target = out / f.relative_to(src)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(f.read_bytes())
                copied += 1
        return copied

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
        """Scan the output dir and import files into media/novel libraries.

        Raises NoContentError when the result is empty or only a webpage shell
        and the tool is not an explicit page archiver."""
        imported = 0
        root = (
            Path(out_dir) if out_dir.startswith(config.DATA_DIR.as_posix())
            else config.DATA_DIR / out_dir.lstrip("./")
        )
        base = root if root.exists() else config.DOWNLOADS_DIR / task_id
        if not base.exists():
            return 0
        if spec.name == "so-novel":
            await self._harvest_sonovel_artifacts(task_id, out_dir)
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
            if imported == 0:
                raise NoContentError("工具执行成功但未下载到可导入的章节内容")
            return imported
        # media: classify files
        kind_map = {
            ".jpg": "image", ".jpeg": "image", ".png": "image", ".gif": "image", ".webp": "image",
            ".bmp": "image", ".avif": "image", ".svg": "image",
            ".mp4": "video", ".mkv": "video", ".webm": "video", ".mov": "video", ".avi": "video", ".flv": "video",
            ".mp3": "audio", ".m4a": "audio", ".flac": "audio", ".wav": "audio", ".ogg": "audio", ".opus": "audio",
            ".html": "page", ".htm": "page", ".pdf": "doc",
            ".zip": "file", ".rar": "file", ".7z": "file", ".tar": "file", ".gz": "file",
            ".bz2": "file", ".xz": "file", ".tgz": "file", ".apk": "file", ".exe": "file",
            ".msi": "file", ".iso": "file", ".epub": "file",
        }
        # yt-dlp 分离流残留（如 ".f30280.m4a" / ".f100026.mp4"）：ffmpeg 合并成功后
        # 会删除原流；但合并失败或中断时会留下无扩展名/带流 ID 的孤儿文件，跳过导入。
        stream_id_re = re.compile(r"\.f\d+$")
        page_imported = 0
        async with SessionLocal() as db:
            for f in sorted(base.rglob("*")):
                if not f.is_file():
                    continue
                if f.name.startswith(".") or f.suffix.lower() in (".part", ".ytdl", ".tmp", ".json", ".txt", ".log"):
                    continue
                stem = f.stem
                # 跳过未合并的分离流文件（title.f30280.mp4 / title.f30280 之类）
                if stream_id_re.search(stem):
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
                item = MediaItem(
                    media_type=mtype, title=f.stem, source_url=url,
                    file_path=rel, mime_type=_guess_mime(f), file_size=size,
                    extra={"task_id": task_id, "dir": base.name},
                )
                db.add(item)
                imported += 1
                if mtype == "page":
                    page_imported += 1
                # 视频/图片：补时长与缩略图（后台线程执行，不阻塞事件循环）
                if mtype in ("video", "image"):
                    try:
                        await db.flush()
                        from .media_assets import fill_media_assets
                        await fill_media_assets(db, item)
                    except Exception:
                        pass
            await db.commit()
        # 只有网页外壳而没有目标内容：对非网页归档任务按失败处理（继续回退）
        if imported == 0 and spec.category != "page":
            raise NoContentError("工具执行成功但未下载到可导入的内容")
        if imported > 0 and page_imported == imported and spec.category != "page":
            raise NoContentError("只抓取到网页外壳（index.html），未获得目标内容（站点可能不支持或需要代理）")
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
