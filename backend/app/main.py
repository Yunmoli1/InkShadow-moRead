"""MoRead backend entrypoint."""
from __future__ import annotations

import asyncio
import hmac
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .database import init_db
from .routers import media, novels, opds, settings, tasks, tools


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .services.applog import get_logger, setup_logging

    setup_logging()
    applog = get_logger("app")
    applog.info("MoRead starting (data dir: %s)", config.DATA_DIR, extra={"event": "startup"})
    config.ensure_dirs()
    await init_db()
    # 任务接管：排队中的重新入队，运行中的标记中断（可重试）
    from .services.task_manager import manager

    requeued = await manager.takeover_on_startup()
    if requeued:
        print(f"[MoRead] 服务重启后已重新入队 {requeued} 个排队任务")
    # 追更订阅后台循环
    from .services.updater import auto_loop

    updater_task = asyncio.create_task(auto_loop())
    # systemd watchdog（仅 NOTIFY_SOCKET 存在时生效）
    from .services import sd_notify

    await sd_notify.ready()
    watchdog_task = sd_notify.start_watchdog()
    yield
    applog.info("MoRead shutting down", extra={"event": "shutdown"})
    updater_task.cancel()
    if watchdog_task:
        watchdog_task.cancel()


app = FastAPI(
    title="墨读 MoRead API",
    description="个人本地知识库：通过调度专业开源工具实现小说/图片/音频/视频/网页的获取、管理与预览。",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local-only app; frontend may run on any local port
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tools.router)
app.include_router(tasks.router)
app.include_router(novels.router)
app.include_router(media.router)
app.include_router(settings.router)
app.include_router(opds.router)


# --- 可选访问令牌（局域网访问保护） ----------------------------------------
# 设置中配置 access_token 后，/api/*（除 health）需要请求头 X-MoRead-Token
# 或查询参数 ?token= 匹配；未设置则完全开放（纯本机使用不受影响）。
from .services.token_guard import current_token as _current_token


@app.middleware("http")
async def access_token_guard(request: Request, call_next):
    path = request.url.path
    # 探针端点免令牌（liveness/readiness 需要被编排层直接访问）
    if path.startswith("/api/") and path not in ("/api/health", "/api/health/ready"):
        token = await _current_token()
        if token:
            provided = (
                request.headers.get("x-moread-token")
                or request.query_params.get("token")
                or ""
            )
            if not provided:
                # OPDS 客户端普遍使用 HTTP Basic（用户名任意，密码=令牌）
                auth = request.headers.get("authorization", "")
                if auth.lower().startswith("basic "):
                    import base64

                    try:
                        decoded = base64.b64decode(auth[6:]).decode("utf-8", errors="replace")
                        provided = decoded.split(":", 1)[1]
                    except Exception:
                        provided = ""
            if not hmac.compare_digest(provided, token):
                from .services.applog import get_logger

                get_logger("auth").warning("access denied: invalid or missing token", extra={
                    "event": "auth-denied", "path": path})
                return JSONResponse({"detail": "需要访问令牌"}, status_code=401)
    return await call_next(request)


@app.get("/api/health", tags=["meta"])
async def health() -> dict:
    """Liveness：进程活着即可响应，不检查任何依赖。"""
    return {"status": "ok", "app": "MoRead", "version": "1.0.0"}


@app.get("/api/health/ready", tags=["meta"])
async def health_ready() -> JSONResponse:
    """Readiness：DB 可查询 + 数据目录可写。不可用时返回 503（编排层据此摘流量）。

    注意：本端点固定免令牌，便于探针/负载均衡器调用。
    """
    checks: dict[str, bool] = {}

    # DB 可查询
    try:
        from .database import SessionLocal
        from sqlalchemy import text

        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as exc:
        from .services.applog import get_logger

        get_logger("health").error("readiness: database check failed: %s", exc)
        checks["database"] = False

    # 数据目录可写
    try:
        probe = config.DATA_DIR / ".readiness-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        checks["data_dir"] = True
    except OSError:
        checks["data_dir"] = False

    ok = all(checks.values())
    return JSONResponse(
        {"status": "ok" if ok else "unavailable", "checks": checks},
        status_code=200 if ok else 503,
    )


# --- serve frontend build (single-binary deployment) -----------------------
STATIC_DIR = config.STATIC_FRONTEND_DIR
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8686, reload=False)
